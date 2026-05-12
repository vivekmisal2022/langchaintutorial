/**
 * Memory MCP tools — numbered entries for agent persistence across sessions.
 *
 * Translated from the Python FastMCP implementation in new-tools.txt.
 * Stores entries as numbered lines in agent_memory.md next to the server root.
 */
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { registerToolWithLogging } from '../utils/toolLogger.js';

// Memory file lives at the project root (next to package.json)
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MEMORY_FILE = path.resolve(__dirname, '..', '..', 'agent_memory.md');

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function loadEntries(): Promise<string[]> {
  if (!existsSync(MEMORY_FILE)) return [];
  const text = await readFile(MEMORY_FILE, 'utf-8');
  const entries: string[] = [];
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    // Strip leading "N. " prefix if present
    const dotIdx = line.indexOf('. ');
    if (dotIdx > 0 && /^\d+$/.test(line.slice(0, dotIdx))) {
      entries.push(line.slice(dotIdx + 2));
    } else {
      entries.push(line);
    }
  }
  return entries;
}

async function saveEntries(entries: string[]): Promise<void> {
  const lines = entries.map((text, i) => `${i + 1}. ${text}`);
  await writeFile(MEMORY_FILE, lines.join('\n') + (lines.length ? '\n' : ''), 'utf-8');
}

// ---------------------------------------------------------------------------
// memory_load
// ---------------------------------------------------------------------------

export function registerMemoryLoadTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'memory_load',
    {
      title: 'Load Memory',
      description:
        "Load the agent's memory file. Returns numbered entries from agent_memory.md. " +
        'Call this at the start of every conversation to recall what you know from previous sessions.',
      inputSchema: {},
    },
    async () => {
      const entries = await loadEntries();
      if (entries.length === 0) {
        return { content: [{ type: 'text' as const, text: '(memory is empty)' }] };
      }
      const text = entries.map((e, i) => `${i + 1}. ${e}`).join('\n');
      return { content: [{ type: 'text' as const, text }] };
    },
  );
}

// ---------------------------------------------------------------------------
// memory_save
// ---------------------------------------------------------------------------

const memorySaveInputSchema = z.object({
  note: z
    .string()
    .describe(
      'A short piece of information to remember. ' +
      "Example: \"Sales text is in ProductSalesDelivery entity, field ProductSalesText\"",
    ),
});

type MemorySaveInput = z.infer<typeof memorySaveInputSchema>;

export function registerMemorySaveTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'memory_save',
    {
      title: 'Save to Memory',
      description:
        "Append a note to the agent's memory. " +
        'Use this after you discover something useful. Keep notes short and factual.',
      inputSchema: memorySaveInputSchema.shape,
    },
    async ({ note }: MemorySaveInput) => {
      const entries = await loadEntries();
      entries.push(note);
      await saveEntries(entries);
      const text = `Saved as entry ${entries.length}: ${note}`;
      return { content: [{ type: 'text' as const, text }] };
    },
  );
}

// ---------------------------------------------------------------------------
// memory_delete
// ---------------------------------------------------------------------------

const memoryDeleteInputSchema = z.object({
  entry_id: z
    .number()
    .int()
    .positive()
    .describe('The entry number to delete (as shown by memory_load). Example: 2 — deletes the second entry.'),
});

type MemoryDeleteInput = z.infer<typeof memoryDeleteInputSchema>;

export function registerMemoryDeleteTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'memory_delete',
    {
      title: 'Delete Memory Entry',
      description:
        'Delete a memory entry by its number. Use memory_load first to see current entries.',
      inputSchema: memoryDeleteInputSchema.shape,
    },
    async ({ entry_id }: MemoryDeleteInput) => {
      const entries = await loadEntries();
      if (entries.length === 0) {
        return { content: [{ type: 'text' as const, text: 'Memory is empty — nothing to delete.' }] };
      }
      if (entry_id < 1 || entry_id > entries.length) {
        return {
          content: [
            { type: 'text' as const, text: `Invalid entry ID ${entry_id}. Valid range: 1–${entries.length}.` },
          ],
        };
      }
      const removed = entries.splice(entry_id - 1, 1)[0];
      await saveEntries(entries);
      const text = `Deleted entry ${entry_id}: ${removed}`;
      return { content: [{ type: 'text' as const, text }] };
    },
  );
}
