/**
 * Component to display active tool calls as status indicators.
 */
import { FlexBox, Text, BusyIndicator } from '@ui5/webcomponents-react';
import type { ActiveTool } from '../contexts/ChatContext';

interface ToolStatusIndicatorProps {
  tools: ActiveTool[];
}

const TOOL_DISPLAY_NAMES: Record<string, { label: string; icon: string }> = {
  // Document/RAG tools
  search_document_headers: { label: 'Searching documents', icon: '📄' },
  search_document_content: { label: 'Reading document content', icon: '📖' },
  // Web tools
  web_search: { label: 'Searching the web', icon: '🔍' },
  web_research: { label: 'Researching online', icon: '🌐' },
  // S/4HANA Product API tools
  search_product_descriptions: { label: 'Searching product descriptions', icon: '🔍' },
  query_products: { label: 'Querying products', icon: '📦' },
  product_api: { label: 'Calling Product API', icon: '🔗' },
  stock_api: { label: 'Checking material stock', icon: '📊' },
  get_product_api_documentation: { label: 'Reading API docs', icon: '📚' },
  // Memory tools
  memory_load: { label: 'Loading memory', icon: '🧠' },
  memory_save: { label: 'Saving to memory', icon: '💾' },
  memory_delete: { label: 'Updating memory', icon: '🗑️' },
  // Time/location
  get_time_and_place: { label: 'Getting time and location', icon: '🕐' },
  // MCP resource tools
  read_resource: { label: 'Reading resource', icon: '📚' },
  list_resources: { label: 'Listing resources', icon: '📋' },
  // Generic fallback
  default: { label: 'Processing', icon: '⚙️' },
};

function getToolDisplay(toolName: string): { label: string; icon: string } {
  return TOOL_DISPLAY_NAMES[toolName] || {
    label: toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    icon: '⚙️'
  };
}

export function ToolStatusIndicator({ tools }: ToolStatusIndicatorProps) {
  if (tools.length === 0) return null;

  return (
    <FlexBox
      direction="Column"
      style={{
        gap: '0.5rem',
        marginBottom: '0.75rem',
      }}
    >
      {tools.map((tool) => {
        const display = getToolDisplay(tool.name);
        return (
          <FlexBox
            key={tool.id}
            direction="Row"
            alignItems="Center"
            style={{
              gap: '0.75rem',
              padding: '0.5rem 0.75rem',
              borderRadius: '0.5rem',
              backgroundColor: 'var(--sapInformationBackground)',
              border: '1px solid var(--sapInformationBorderColor)',
              animation: 'fadeIn 0.2s ease-in-out',
            }}
          >
            <Text style={{ fontSize: '1rem' }}>{display.icon}</Text>
            <BusyIndicator active size="S" />
            <Text
              style={{
                color: 'var(--sapInformativeTextColor)',
                fontSize: '0.875rem',
                fontWeight: '500',
              }}
            >
              {display.label}
            </Text>
          </FlexBox>
        );
      })}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </FlexBox>
  );
}
