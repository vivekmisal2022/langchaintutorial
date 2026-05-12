import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

import { registerToolWithLogging } from '../utils/toolLogger.js';

// Input schema for the tool (optional timezone override)
const timeAndPlaceInputSchema = z.object({
  timezone: z
    .string()
    .optional()
    .describe('Optional IANA timezone to use instead of system default (e.g., "Asia/Tokyo", "America/New_York")'),
});

const timeAndPlaceInputSchemaShape = timeAndPlaceInputSchema.shape;

// Output schema for the tool
const timeAndPlaceResultSchema = z.object({
  iso_datetime: z.string().describe('Current local date and time in ISO 8601 format'),
  timezone: z.string().describe('IANA timezone identifier, e.g. Asia/Tokyo'),
  country: z.string().describe('Country inferred from timezone, e.g. Japan'),
  city: z.string().describe('City, usually the capital of the inferred country, e.g. Tokyo'),
  display: z
    .string()
    .describe('Human‑readable summary like "2025-01-01 10:00 in Tokyo, Japan (Asia/Tokyo)"'),
});

const timeAndPlaceResultSchemaShape = timeAndPlaceResultSchema.shape;

// Minimal timezone → (country, capital) mapping for common zones
// Fallbacks are handled when a mapping is not found.
const TIMEZONE_MAPPING: Record<string, { country: string; city: string }> = {
  'Asia/Tokyo': { country: 'Japan', city: 'Tokyo' },
  'Europe/Berlin': { country: 'Germany', city: 'Berlin' },
  'Europe/London': { country: 'United Kingdom', city: 'London' },
  'America/New_York': { country: 'United States', city: 'Washington, D.C.' },
  'America/Los_Angeles': { country: 'United States', city: 'Washington, D.C.' },
  'Europe/Paris': { country: 'France', city: 'Paris' },
  'Europe/Rome': { country: 'Italy', city: 'Rome' },
  'Asia/Seoul': { country: 'South Korea', city: 'Seoul' },
  'Asia/Shanghai': { country: 'China', city: 'Beijing' },
  'Asia/Singapore': { country: 'Singapore', city: 'Singapore' },
  'Asia/Hong_Kong': { country: 'Hong Kong', city: 'Hong Kong' },
  'Australia/Sydney': { country: 'Australia', city: 'Canberra' },
};

function formatLocalIsoWithOffset(date: Date, timeZone: string): string {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  const parts = formatter.formatToParts(date);
  const lookup: Record<string, string> = {};

  for (const part of parts) {
    if (part.type !== 'literal') {
      lookup[part.type] = part.value;
    }
  }

  const year = lookup.year ?? '0000';
  const month = lookup.month ?? '01';
  const day = lookup.day ?? '01';
  const hour = lookup.hour ?? '00';
  const minute = lookup.minute ?? '00';
  const second = lookup.second ?? '00';

  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absOffset = Math.abs(offsetMinutes);
  const offsetHours = String(Math.floor(absOffset / 60)).padStart(2, '0');
  const offsetMins = String(absOffset % 60).padStart(2, '0');

  return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${offsetHours}:${offsetMins}`;
}

function inferTimeAndPlace(overrideTimezone?: string) {
  const timeZone = overrideTimezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

  const now = new Date();

  const mapping = TIMEZONE_MAPPING[timeZone];

  let country = 'Unknown country';
  let city = 'Unknown city';

  if (mapping) {
    country = mapping.country;
    city = mapping.city;
  } else {
    // Fallback: use the last segment of the timezone as city‑like name
    const parts = timeZone.split('/');
    const lastSegment = parts[parts.length - 1] || 'Unknown';
    city = lastSegment.replace(/_/g, ' ');
  }

  const isoLocal = formatLocalIsoWithOffset(now, timeZone);

  const display = `${isoLocal.replace('T', ' ')} in ${city}${
    country === 'Unknown country' ? '' : `, ${country}`
  } (${timeZone})`;

  const result = {
    iso_datetime: isoLocal,
    timezone: timeZone,
    country,
    city,
    display,
  };

  return result;
}

export function registerTimeAndPlaceTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'get_time_and_place',
    {
      title: 'Get Time and Place',
      description:
        'Returns the current local date/time and an inferred place (capital city for the country when possible). Optionally accepts a timezone parameter to get time for a specific timezone instead of the system default.',
      inputSchema: timeAndPlaceInputSchemaShape,
      outputSchema: timeAndPlaceResultSchemaShape,
    },
    async (args: { timezone?: string }) => {
      const output = inferTimeAndPlace(args.timezone);

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(output, null, 2),
          },
        ],
        structuredContent: output,
      };
    },
  );
}
