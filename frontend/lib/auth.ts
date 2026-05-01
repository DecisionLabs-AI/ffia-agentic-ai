export interface AuthUser {
  user_id: string;
  username: string;
  display_name: string;
  restaurant_name?: string | null;
}

const AUTH_USER_KEY = "ffia_auth_user";

export function getCurrentUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthUser>;
    if (!parsed.user_id || !parsed.username) {
      localStorage.removeItem(AUTH_USER_KEY);
      return null;
    }
    return {
      user_id: String(parsed.user_id),
      username: String(parsed.username),
      display_name: String(parsed.display_name || parsed.username),
      restaurant_name: parsed.restaurant_name ? String(parsed.restaurant_name) : null,
    };
  } catch {
    localStorage.removeItem(AUTH_USER_KEY);
    return null;
  }
}

export function setCurrentUser(user: AuthUser): void {
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

export function isAuthenticated(): boolean {
  return getCurrentUser() !== null;
}

export function logout(): void {
  localStorage.removeItem(AUTH_USER_KEY);
}
