import { jwtDecode } from 'jwt-decode';
import { setTokens, clearTokens, getAccessToken, getRefreshToken } from './api';

export interface DecodedToken {
  sub: string;        // username
  role: string;
  user_id: string;
  exp: number;
  type: string;
}

export function getDecodedToken(): DecodedToken | null {
  const token = getAccessToken();
  if (!token) return null;
  try {
    return jwtDecode<DecodedToken>(token);
  } catch {
    return null;
  }
}

export function isTokenExpired(token: DecodedToken): boolean {
  return Date.now() / 1000 >= token.exp;
}

export function isAuthenticated(): boolean {
  const decoded = getDecodedToken();
  if (!decoded) return false;
  return !isTokenExpired(decoded);
}

export function getCurrentUser(): { username: string; role: string; userId: string } | null {
  const decoded = getDecodedToken();
  if (!decoded) return null;
  return { username: decoded.sub, role: decoded.role, userId: decoded.user_id };
}

export function storeTokens(access: string, refresh: string) {
  setTokens(access, refresh);
}

export function logout() {
  clearTokens();
  if (typeof window !== 'undefined') window.location.href = '/login';
}
