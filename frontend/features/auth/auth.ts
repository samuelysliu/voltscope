export const MEMBER_TOKEN_KEY = "voltscope_member_token";

export function getMemberToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(MEMBER_TOKEN_KEY);
}

export function setMemberToken(token: string): void {
  localStorage.setItem(MEMBER_TOKEN_KEY, token);
}

export function clearMemberToken(): void {
  localStorage.removeItem(MEMBER_TOKEN_KEY);
}

export function authApiBase(): string {
  return "/api/v1";
}
