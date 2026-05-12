import { ThemeProvider } from './contexts/ThemeContext';
import { ChatProvider } from './contexts/ChatContext';
import { UserProvider } from './contexts/UserContext';
import { AppShell } from './components/AppShell';

function App() {
  return (
    <ThemeProvider>
      <UserProvider>
        <ChatProvider>
          <AppShell />
        </ChatProvider>
      </UserProvider>
    </ThemeProvider>
  );
}

export default App;
