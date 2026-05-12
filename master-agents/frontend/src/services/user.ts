/**
 * User service for fetching user information from the backend.
 */
import type { UserInfo } from '../types/index';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Fetch current user information from the backend.
 * Returns user details extracted from the JWT token.
 */
export async function fetchUserInfo(): Promise<UserInfo> {
  const response = await fetch(`${API_BASE_URL}/api/user/me`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user info: ${response.status}`);
  }

  return response.json();
}

/**
 * Storage key for user avatar in localStorage.
 */
const AVATAR_STORAGE_KEY = 'user-avatar';

/**
 * Get avatar URL from localStorage.
 */
export function getStoredAvatar(): string | null {
  return localStorage.getItem(AVATAR_STORAGE_KEY);
}

/**
 * Store avatar URL in localStorage.
 */
export function storeAvatar(dataUrl: string): void {
  localStorage.setItem(AVATAR_STORAGE_KEY, dataUrl);
}

/**
 * Remove avatar from localStorage.
 */
export function removeAvatar(): void {
  localStorage.removeItem(AVATAR_STORAGE_KEY);
}

/**
 * Convert a File to a base64 data URL.
 */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Resize an image to a maximum dimension while maintaining aspect ratio.
 */
export function resizeImage(dataUrl: string, maxSize: number = 128): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      let width = img.width;
      let height = img.height;

      // Scale down if larger than maxSize
      if (width > height) {
        if (width > maxSize) {
          height = Math.round((height * maxSize) / width);
          width = maxSize;
        }
      } else {
        if (height > maxSize) {
          width = Math.round((width * maxSize) / height);
          height = maxSize;
        }
      }

      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Could not get canvas context'));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = reject;
    img.src = dataUrl;
  });
}
