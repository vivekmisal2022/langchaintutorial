/**
 * Main application shell with ShellBar and layout.
 */
import {
  ShellBar,
  Avatar,
  FlexBox,
  Menu,
  MenuItem,
  Icon,
  UserMenu,
  UserMenuItem,
  UserMenuAccount,
  UserSettingsDialog,
  UserSettingsItem,
  UserSettingsView,
  UserSettingsAppearanceView,
  UserSettingsAppearanceViewGroup,
  UserSettingsAppearanceViewItem,
  Text,
  Label,
  Title,
} from '@ui5/webcomponents-react';
import type {
  UserMenuDomRef,
  ShellBarPropTypes,
  UserMenuPropTypes,
  UserSettingsDialogDomRef,
  UserSettingsAppearanceViewPropTypes,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/palette.js';
import '@ui5/webcomponents-icons/dist/document.js';
import '@ui5/webcomponents-icons/dist/discussion.js';
import '@ui5/webcomponents-icons/dist/slim-arrow-down.js';
import '@ui5/webcomponents-icons/dist/upload.js';
import '@ui5/webcomponents-icons/dist/delete.js';
import '@ui5/webcomponents-icons/dist/action-settings.js';
import '@ui5/webcomponents-icons/dist/user-settings.js';
import '@ui5/webcomponents-icons/dist/person-placeholder.js';
import { ChatInterface } from './ChatInterface';
import { DocumentManagement } from './DocumentManagement';
import { useState, useRef, useCallback, KeyboardEvent } from 'react';
import { ChatHistorySidebar } from './ChatHistorySidebar';
import { useUser } from '../contexts/UserContext';
import { useTheme } from '../contexts/ThemeContext';
import { setTheme } from '@ui5/webcomponents-base/dist/config/Theme.js';

type ViewMode = 'chat' | 'documents';

export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('chat');
  const [showViewMenu, setShowViewMenu] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  const userMenuRef = useRef<UserMenuDomRef>(null);
  const settingsDialogRef = useRef<UserSettingsDialogDomRef>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { user, avatarUrl, uploadAvatar, clearAvatar } = useUser();
  const { setThemeMode, effectiveTheme } = useTheme();

  const userInitials = user?.initials || 'U';
  const userName = user?.full_name || 'User';
  const userEmail = user?.email || '';

  // Get the current UI5 theme key
  const currentThemeKey = effectiveTheme === 'dark' ? 'sap_horizon_dark' : 'sap_horizon';

  const handleProfileClick = useCallback<NonNullable<ShellBarPropTypes['onProfileClick']>>((e) => {
    if (userMenuRef.current) {
      userMenuRef.current.opener = e.detail.targetRef;
      setUserMenuOpen(true);
    }
  }, []);

  const handleUserMenuClose = useCallback(() => {
    setUserMenuOpen(false);
  }, []);

  const handleFileInputChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.type.startsWith('image/')) {
        try {
          await uploadAvatar(file);
        } catch (err) {
          console.error('Failed to upload avatar:', err);
        }
      }
    }
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [uploadAvatar]);

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleUserMenuItemClick = useCallback<NonNullable<UserMenuPropTypes['onItemClick']>>((e) => {
    const item = e.detail?.item;
    const isSettingsItem = item?.getAttribute('data-settings') === 'true';
    const isUploadItem = item?.getAttribute('data-upload') === 'true';
    const isRemoveItem = item?.getAttribute('data-remove') === 'true';

    if (isSettingsItem) {
      setUserMenuOpen(false);
      setSettingsDialogOpen(true);
    } else if (isUploadItem) {
      handleUploadClick();
    } else if (isRemoveItem) {
      clearAvatar();
    }
  }, [handleUploadClick, clearAvatar]);

  const handleSettingsDialogClose = useCallback(() => {
    setSettingsDialogOpen(false);
  }, []);

  // Handle theme selection from the appearance view
  const handleThemeSelect = useCallback<NonNullable<UserSettingsAppearanceViewPropTypes['onSelectionChange']>>((e) => {
    const selectedItem = e.detail?.item;
    const themeKey = selectedItem?.itemKey;
    if (themeKey) {
      // Apply the UI5 theme directly
      setTheme(themeKey);
      // Map to our theme mode for persistence
      if (themeKey === 'sap_horizon') {
        setThemeMode('light');
      } else if (themeKey === 'sap_horizon_dark') {
        setThemeMode('dark');
      }
      // For high contrast themes, keep the selection but don't change our simple mode
    }
  }, [setThemeMode]);

  return (
    <FlexBox
      direction="Column"
      style={{
        height: '100%',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Hidden file input for avatar upload */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleFileInputChange}
      />

      {/* Shell Bar with clickable logo/title */}
      <ShellBar
        primaryTitle="Super Agent"
        secondaryTitle={viewMode === 'chat' ? 'Your Personal Assistant' : 'Document Management'}
        logo={
          <div
            id="logoMenuButton"
            role="button"
            tabIndex={0}
            aria-haspopup="menu"
            aria-expanded={showViewMenu}
            onClick={() => setShowViewMenu(!showViewMenu)}
            onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                setShowViewMenu(!showViewMenu);
              }
            }}
            style={{
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              padding: '0.25rem 0.5rem',
              borderRadius: '0.375rem',
              background: showViewMenu ? 'var(--sapShellColor)' : 'transparent',
            }}
          >
            <img src="/sap-logo.svg" alt="SAP Logo" style={{ height: '2rem' }} />
            <Icon name="slim-arrow-down" style={{ color: 'var(--sapShell_TextColor)' }} />
          </div>
        }
        onProfileClick={handleProfileClick}
        profile={
          avatarUrl ? (
            <Avatar colorScheme="Accent1">
              <img
                src={avatarUrl}
                alt="User avatar"
                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }}
              />
            </Avatar>
          ) : (
            <Avatar initials={userInitials} colorScheme="Accent1" />
          )
        }
      />

      {/* View Selection Menu */}
      <Menu
        open={showViewMenu}
        opener="logoMenuButton"
        onClose={() => setShowViewMenu(false)}
        onItemClick={(e) => {
          const text = e.detail.text;
          if (text === 'Chat') {
            setViewMode('chat');
          } else if (text === 'Document Management') {
            setViewMode('documents');
          }
          setShowViewMenu(false);
        }}
      >
        <MenuItem icon="discussion" text="Chat" />
        <MenuItem icon="document" text="Document Management" />
      </Menu>

      {/* User Menu */}
      <UserMenu
        ref={userMenuRef}
        open={userMenuOpen}
        onClose={handleUserMenuClose}
        onItemClick={handleUserMenuItemClick}
        showManageAccount={false}
        showOtherAccounts={false}
        accounts={
          <UserMenuAccount
            slot="accounts"
            titleText={userName}
            subtitleText={userEmail}
            description="Your Personal Assistant"
            avatarInitials={avatarUrl ? undefined : userInitials}
            avatarSrc={avatarUrl || undefined}
            selected
          />
        }
      >
        <UserMenuItem
          data-settings="true"
          icon="action-settings"
          text="Settings"
        />
        <UserMenuItem
          data-upload="true"
          icon="upload"
          text="Upload Avatar"
        />
        {avatarUrl && (
          <UserMenuItem
            data-remove="true"
            icon="delete"
            text="Remove Avatar"
          />
        )}
      </UserMenu>

      {/* User Settings Dialog */}
      <UserSettingsDialog
        ref={settingsDialogRef}
        open={settingsDialogOpen}
        onClose={handleSettingsDialogClose}
      >
        <UserSettingsItem
          headerText="User Account"
          icon="user-settings"
          text="User Account"
          tooltip="User Account"
          tabs={
            <UserSettingsView>
              <FlexBox
                direction="Column"
                alignItems="Center"
                style={{ padding: '1rem', gap: '1rem' }}
              >
                {avatarUrl ? (
                  <Avatar size="XL" colorScheme="Accent1">
                    <img
                      src={avatarUrl}
                      alt="User avatar"
                      style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }}
                    />
                  </Avatar>
                ) : (
                  <Avatar size="XL" initials={userInitials} colorScheme="Accent1" />
                )}
                <Title level="H3">{userName}</Title>
                <FlexBox direction="Column" style={{ gap: '0.5rem', width: '100%' }}>
                  <FlexBox style={{ gap: '0.5rem' }}>
                    <Label>Name:</Label>
                    <Text>{userName}</Text>
                  </FlexBox>
                  <FlexBox style={{ gap: '0.5rem' }}>
                    <Label>Email:</Label>
                    <Text>{userEmail}</Text>
                  </FlexBox>
                </FlexBox>
              </FlexBox>
            </UserSettingsView>
          }
        />
        <UserSettingsItem
          headerText="Appearance"
          icon="palette"
          text="Appearance"
          tooltip="Appearance"
        >
          <UserSettingsAppearanceView
            text="Themes"
            onSelectionChange={handleThemeSelect}
          >
            <UserSettingsAppearanceViewGroup headerText="SAP Horizon">
              <UserSettingsAppearanceViewItem
                itemKey="sap_horizon"
                text="SAP Morning Horizon (Light)"
                selected={currentThemeKey === 'sap_horizon'}
              />
              <UserSettingsAppearanceViewItem
                itemKey="sap_horizon_dark"
                text="SAP Evening Horizon (Dark)"
                selected={currentThemeKey === 'sap_horizon_dark'}
              />
              <UserSettingsAppearanceViewItem
                itemKey="sap_horizon_hcb"
                text="SAP Horizon High Contrast Black"
              />
              <UserSettingsAppearanceViewItem
                itemKey="sap_horizon_hcw"
                text="SAP Horizon High Contrast White"
              />
            </UserSettingsAppearanceViewGroup>
          </UserSettingsAppearanceView>
        </UserSettingsItem>
      </UserSettingsDialog>

      {/* Main Content */}
      <FlexBox
        direction="Row"
        style={{
          flex: 1,
          overflow: 'hidden',
          backgroundColor: 'var(--sapBackgroundColor)',
        }}
      >
        {/* Show sidebar only in chat mode */}
        {viewMode === 'chat' && (
          <ChatHistorySidebar
            collapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
        )}

        <FlexBox
          direction="Column"
          style={{
            flex: 1,
            overflow: 'hidden',
            minWidth: 0,
          }}
        >
          {viewMode === 'chat' ? <ChatInterface /> : <DocumentManagement />}
        </FlexBox>
      </FlexBox>
    </FlexBox>
  );
}
