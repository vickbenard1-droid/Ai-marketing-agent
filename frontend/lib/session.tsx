"use client";

/**
 * Minimal client-side session store.
 *
 * Week 1 scope note: tokens are kept in memory + localStorage, and auth
 * state is resolved client-side only. There is no server-side session
 * cookie / middleware-based route protection yet — that's a deliberate
 * gap for a later week (see docs/README.md "not built yet"), not an
 * oversight. Don't build additional features assuming SSR auth exists.
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  getCurrentUser,
  listOrganizations,
  logout as logoutRequest,
  type OrganizationPublic,
  type UserPublic,
} from "./api";

const ACCESS_TOKEN_KEY = "ama_access_token";
const REFRESH_TOKEN_KEY = "ama_refresh_token";
const ACTIVE_ORG_KEY = "ama_active_org_id";

interface SessionContextValue {
  user: UserPublic | null;
  organizations: OrganizationPublic[];
  activeOrganization: OrganizationPublic | null;
  activeOrganizationId: string | null;
  accessToken: string | null;
  isLoading: boolean;
  setSession: (tokens: { access_token: string; refresh_token: string }) => Promise<void>;
  setActiveOrganizationId: (id: string) => void;
  refreshOrganizations: () => Promise<void>;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationPublic[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function hydrateFromToken(token: string) {
    const [currentUser, orgs] = await Promise.all([
      getCurrentUser(token),
      listOrganizations(token),
    ]);
    setUser(currentUser);
    setOrganizations(orgs);

    const storedOrgId =
      typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_ORG_KEY) : null;
    const stillValid = orgs.find((o) => o.id === storedOrgId);
    const nextActiveId = stillValid ? stillValid.id : orgs[0]?.id ?? null;
    setActiveOrgId(nextActiveId);
    if (nextActiveId) {
      window.localStorage.setItem(ACTIVE_ORG_KEY, nextActiveId);
    }
  }

  useEffect(() => {
    const stored = window.localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    setAccessToken(stored);
    hydrateFromToken(stored)
      .catch(() => {
        // Token is invalid/expired — clear it rather than leaving the UI
        // in a half-authenticated state.
        window.localStorage.removeItem(ACCESS_TOKEN_KEY);
        window.localStorage.removeItem(REFRESH_TOKEN_KEY);
        setAccessToken(null);
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function setSession(tokens: { access_token: string; refresh_token: string }) {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    setAccessToken(tokens.access_token);
    await hydrateFromToken(tokens.access_token);
  }

  function setActiveOrganizationId(id: string) {
    setActiveOrgId(id);
    window.localStorage.setItem(ACTIVE_ORG_KEY, id);
  }

  async function refreshOrganizations() {
    if (!accessToken) return;
    const orgs = await listOrganizations(accessToken);
    setOrganizations(orgs);
  }

  async function refreshUser() {
    if (!accessToken) return;
    const currentUser = await getCurrentUser(accessToken);
    setUser(currentUser);
  }

  async function logout() {
    const refreshToken = window.localStorage.getItem(REFRESH_TOKEN_KEY);
    // Best-effort server-side revocation — if it fails (network issue,
    // already-expired token), still clear local state so the person is
    // signed out on this device regardless.
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken);
      } catch {
        // intentionally swallowed — see comment above
      }
    }
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    window.localStorage.removeItem(REFRESH_TOKEN_KEY);
    window.localStorage.removeItem(ACTIVE_ORG_KEY);
    setAccessToken(null);
    setUser(null);
    setOrganizations([]);
    setActiveOrgId(null);
  }

  const activeOrganization = organizations.find((o) => o.id === activeOrgId) ?? null;

  return (
    <SessionContext.Provider
      value={{
        user,
        organizations,
        activeOrganization,
        activeOrganizationId: activeOrgId,
        accessToken,
        isLoading,
        setSession,
        setActiveOrganizationId,
        refreshOrganizations,
        refreshUser,
        logout,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}
