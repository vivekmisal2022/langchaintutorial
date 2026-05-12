import { useCallback, useMemo, useState } from 'react';
import {
  Button,
  FlexBox,
  Input,
  List,
  ListItemStandard,
  Text,
  Title,
  type InputPropTypes,
  type ListPropTypes,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/add.js';
import '@ui5/webcomponents-icons/dist/delete.js';
import '@ui5/webcomponents-icons/dist/refresh.js';
import '@ui5/webcomponents-icons/dist/menu.js';
import '@ui5/webcomponents-icons/dist/message-popup.js';
import { useChat } from '../contexts/ChatContext';

function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'short' }).format(date);
}

interface ChatHistorySidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function ChatHistorySidebar({ collapsed, onToggleCollapse }: ChatHistorySidebarProps) {
  const {
    sessions,
    activeSessionId,
    loadSession,
    createSession,
    deleteSession,
    refreshSessions,
  } = useChat();
  const [search, setSearch] = useState('');
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);

  const filteredSessions = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) {
      return sessions;
    }
    return sessions.filter((session) =>
      session.title.toLowerCase().includes(term) || session.last_message.toLowerCase().includes(term)
    );
  }, [search, sessions]);

  const handleSelectionChange: ListPropTypes['onSelectionChange'] = (event) => {
    const item = event.detail.selectedItems?.[0];
    const sessionId = item?.dataset?.sessionId;
    if (sessionId) {
      void loadSession(sessionId);
    }
  };

  const handleSearchInput = useCallback<NonNullable<InputPropTypes['onInput']>>((event) => {
    const value = event.target.value ?? '';
    setSearch(value);
  }, []);

  const handleCreateSession = async () => {
    await createSession();
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteSession(sessionId);
  };

  return (
    <FlexBox
      direction="Column"
      style={{
        width: collapsed ? '3rem' : '280px',
        maxWidth: collapsed ? '3rem' : '280px',
        minWidth: collapsed ? '3rem' : '240px',
        borderRight: '1px solid var(--sapList_BorderColor)',
        backgroundColor: 'var(--sapShellColor)',
        padding: collapsed ? '0.75rem 0.25rem' : '0.75rem',
        gap: '0.5rem',
        flexShrink: 0,
        transition: 'width 0.3s ease, min-width 0.3s ease, max-width 0.3s ease',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <FlexBox justifyContent="SpaceBetween" alignItems="Center">
        {collapsed ? (
          <Button
            icon="menu"
            design="Transparent"
            tooltip="Expand Sidebar"
            onClick={onToggleCollapse}
            style={{ width: '100%' }}
          />
        ) : (
          <>
            <Title level="H5" style={{ whiteSpace: 'nowrap' }}>Chat History</Title>
            <FlexBox style={{ gap: '0.125rem' }}>
              <Button icon="menu" design="Transparent" tooltip="Collapse Sidebar" onClick={onToggleCollapse} />
              <Button icon="refresh" design="Transparent" tooltip="Refresh" onClick={() => void refreshSessions()} />
              <Button icon="add" design="Emphasized" tooltip="New Chat" onClick={handleCreateSession} />
            </FlexBox>
          </>
        )}
      </FlexBox>

      {!collapsed && (
        <>
          {/* Search */}
          <Input
            value={search}
            onInput={handleSearchInput}
            placeholder="Search conversations..."
            showClearIcon
            style={{ width: '100%' }}
          />

          {/* Session List */}
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
            {filteredSessions.length === 0 ? (
              <FlexBox
                direction="Column"
                alignItems="Center"
                justifyContent="Center"
                style={{ padding: '1.5rem 1rem', gap: '0.5rem', textAlign: 'center' }}
              >
                <Text style={{ color: 'var(--sapContent_LabelColor)' }}>
                  No conversations yet.
                </Text>
                <Text style={{ fontSize: '0.8125rem', color: 'var(--sapContent_LabelColor)' }}>
                  Click + to start a new chat.
                </Text>
              </FlexBox>
            ) : (
              <List
                selectionMode="Single"
                onSelectionChange={handleSelectionChange}
                noDataText="No conversations"
                style={{
                  '--_ui5-v2-5-0_list_item_selection_btn_visibility': 'hidden',
                } as React.CSSProperties}
              >
                {filteredSessions.map((session) => {
                  const isActive = session.session_id === activeSessionId;
                  const isHovered = hoveredSessionId === session.session_id;

                  return (
                    <ListItemStandard
                      key={session.session_id}
                      data-session-id={session.session_id}
                      selected={isActive}
                      description={`${session.message_count} messages · ${formatRelativeTime(new Date(session.timestamp))}`}
                      onMouseEnter={() => setHoveredSessionId(session.session_id)}
                      onMouseLeave={() => setHoveredSessionId(null)}
                      style={{
                        borderRadius: '0.375rem',
                        marginBottom: '2px',
                      }}
                    >
                      <FlexBox
                        justifyContent="SpaceBetween"
                        alignItems="Center"
                        style={{ width: '100%', minWidth: 0 }}
                      >
                        <Text
                          style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            flex: 1,
                            minWidth: 0,
                            fontSize: '0.875rem',
                            fontWeight: isActive ? '600' : '400',
                          }}
                        >
                          {session.title || 'Untitled chat'}
                        </Text>
                        {isHovered && (
                          <Button
                            icon="delete"
                            design="Transparent"
                            tooltip="Delete chat"
                            onClick={(e) => void handleDeleteSession(session.session_id, e as unknown as React.MouseEvent)}
                            style={{
                              flexShrink: 0,
                              marginLeft: '0.25rem',
                              minWidth: 'unset',
                              padding: '0',
                              height: '1.5rem',
                              width: '1.5rem',
                            }}
                          />
                        )}
                      </FlexBox>
                    </ListItemStandard>
                  );
                })}
              </List>
            )}
          </div>
        </>
      )}
    </FlexBox>
  );
}
