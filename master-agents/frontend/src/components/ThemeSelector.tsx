/**
 * Theme selector component for switching between light/dark/system themes.
 */
import { Card, CardHeader, RadioButton, FlexBox } from '@ui5/webcomponents-react';
import { useTheme } from '../contexts/ThemeContext';
import type { ThemeMode } from '../types';

interface ThemeSelectorProps {
  onClose: () => void;
}

export function ThemeSelector({ onClose: _onClose }: ThemeSelectorProps) {
  const { themeMode, setThemeMode } = useTheme();

  const handleThemeChange = (mode: ThemeMode) => {
    setThemeMode(mode);
  };

  return (
    <Card
      header={<CardHeader titleText="Theme Settings" />}
      style={{
        width: '300px',
        boxShadow: 'var(--sapContent_Shadow2)',
      }}
    >
      <FlexBox
        direction="Column"
        style={{
          padding: '1rem',
          gap: '0.75rem',
        }}
      >
        <RadioButton
          text="Light Theme"
          checked={themeMode === 'light'}
          onChange={() => handleThemeChange('light')}
          name="theme"
        />
        <RadioButton
          text="Dark Theme"
          checked={themeMode === 'dark'}
          onChange={() => handleThemeChange('dark')}
          name="theme"
        />
        <RadioButton
          text="System Default"
          checked={themeMode === 'system'}
          onChange={() => handleThemeChange('system')}
          name="theme"
        />
      </FlexBox>
    </Card>
  );
}
