/**
 * User context for managing user information and avatar.
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { UserInfo } from '../types/index';
import {
  fetchUserInfo,
  getStoredAvatar,
  storeAvatar,
  removeAvatar,
  fileToDataUrl,
  resizeImage
} from '../services/user';

interface UserContextType {
  user: UserInfo | null;
  avatarUrl: string | null;
  isLoading: boolean;
  error: string | null;
  uploadAvatar: (file: File) => Promise<void>;
  clearAvatar: () => void;
  refetchUser: () => Promise<void>;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

interface UserProviderProps {
  children: ReactNode;
}

export function UserProvider({ children }: UserProviderProps) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUser = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const userInfo = await fetchUserInfo();
      setUser(userInfo);

      // Load stored avatar
      const storedAvatar = getStoredAvatar();
      setAvatarUrl(storedAvatar);
    } catch (err) {
      console.error('Failed to load user info:', err);
      setError(err instanceof Error ? err.message : 'Failed to load user');

      // Set fallback user for local development
      setUser({
        user_id: 'anonymous',
        email: 'anonymous@local',
        given_name: 'Anonymous',
        family_name: 'User',
        full_name: 'Anonymous User',
        initials: 'AU',
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const uploadAvatar = useCallback(async (file: File) => {
    try {
      // Convert to data URL
      const dataUrl = await fileToDataUrl(file);

      // Resize to 128x128 max
      const resizedUrl = await resizeImage(dataUrl, 128);

      // Store in localStorage
      storeAvatar(resizedUrl);

      // Update state
      setAvatarUrl(resizedUrl);
    } catch (err) {
      console.error('Failed to upload avatar:', err);
      throw err;
    }
  }, []);

  const clearAvatar = useCallback(() => {
    removeAvatar();
    setAvatarUrl(null);
  }, []);

  const refetchUser = useCallback(async () => {
    await loadUser();
  }, [loadUser]);

  return (
    <UserContext.Provider
      value={{
        user,
        avatarUrl,
        isLoading,
        error,
        uploadAvatar,
        clearAvatar,
        refetchUser,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}
