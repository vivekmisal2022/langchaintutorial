/**
 * Main chat interface component.
 */
import { FlexBox, MessageStrip } from '@ui5/webcomponents-react';
import { useChat } from '../contexts/ChatContext';
import { ChatInput } from './ChatInput';
import { ChatMessages } from './ChatMessages';

export function ChatInterface() {
  const { error } = useChat();

  return (
    <FlexBox
      direction="Column"
      style={{
        height: '100%',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Error Message */}
      {error && (
        <MessageStrip
          design="Negative"
          hideCloseButton={false}
          style={{ margin: '1rem' }}
        >
          {error}
        </MessageStrip>
      )}

      {/* Messages Area */}
      <FlexBox
        direction="Column"
        style={{
          flex: 1,
          overflow: 'hidden',
        }}
      >
        <ChatMessages />
      </FlexBox>

      {/* Input Area */}
      <ChatInput />
    </FlexBox>
  );
}
