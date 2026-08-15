"use client";

import { useEffect, useState } from "react";
import { UserMinus } from "lucide-react";
import {
  ApiError,
  inviteMember,
  listMembers,
  listRoles,
  removeMember,
  updateMemberRole,
  type OrganizationMemberPublic,
  type RolePublic,
} from "@/lib/api";
import { useSession } from "@/lib/session";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";

export default function TeamPage() {
  const { accessToken, activeOrganization, activeOrganizationId } = useSession();
  const [members, setMembers] = useState<OrganizationMemberPublic[]>([]);
  const [roles, setRoles] = useState<RolePublic[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [isInviting, setIsInviting] = useState(false);

  const [actionError, setActionError] = useState<string | null>(null);

  async function load() {
    if (!accessToken || !activeOrganizationId) return;
    const [memberList, roleList] = await Promise.all([
      listMembers(accessToken, activeOrganizationId),
      listRoles(accessToken, activeOrganizationId),
    ]);
    setMembers(memberList);
    setRoles(roleList);
    if (!inviteRole && roleList.length > 0) {
      const defaultRole = roleList.find((r) => r.name === "viewer") ?? roleList[roleList.length - 1];
      if (defaultRole) {
        setInviteRole(defaultRole.name);
      }
    }
  }

  useEffect(() => {
    load()
      .catch(() => {})
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, activeOrganizationId]);

  if (!accessToken || !activeOrganizationId) return null;

  async function handleInvite(event: React.FormEvent) {
    event.preventDefault();
    setInviteError(null);
    setIsInviting(true);
    try {
      await inviteMember(accessToken!, activeOrganizationId!, { email: inviteEmail, role_name: inviteRole });
      setInviteEmail("");
      await load();
    } catch (err) {
      setInviteError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't add that person") : "Couldn't add that person"
      );
    } finally {
      setIsInviting(false);
    }
  }

  async function handleRoleChange(memberId: string, roleName: string) {
    setActionError(null);
    try {
      await updateMemberRole(accessToken!, activeOrganizationId!, memberId, roleName);
      await load();
    } catch (err) {
      setActionError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't change role") : "Couldn't change role"
      );
    }
  }

  async function handleRemove(memberId: string) {
    setActionError(null);
    try {
      await removeMember(accessToken!, activeOrganizationId!, memberId);
      await load();
    } catch (err) {
      setActionError(
        err instanceof ApiError ? String(err.detail ?? "Couldn't remove member") : "Couldn't remove member"
      );
    }
  }

  return (
    <>
      <Header title="Team" description={activeOrganization?.name} />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          <section className="rounded-lg border border-ink-100 bg-white p-6 shadow-panel">
            <h2 className="mb-4 text-sm font-semibold text-ink-900">Add a team member</h2>
            <p className="mb-4 text-xs text-ink-500">
              They need an existing account — invite links aren&apos;t available yet.
            </p>
            <form onSubmit={handleInvite} className="flex items-end gap-3">
              <div className="flex-1">
                <Field
                  label="Email"
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="teammate@example.com"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="invite-role" className="text-sm font-medium text-ink-700">
                  Role
                </label>
                <select
                  id="invite-role"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="rounded-md border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 focus:border-ink-500"
                >
                  {roles.map((role) => (
                    <option key={role.id} value={role.name}>
                      {formatRoleName(role.name)}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" disabled={isInviting}>
                {isInviting ? "Adding…" : "Add"}
              </Button>
            </form>
            {inviteError && (
              <p role="alert" className="mt-3 text-sm text-signal">
                {inviteError}
              </p>
            )}
          </section>

          <section className="rounded-lg border border-ink-100 bg-white shadow-panel">
            <h2 className="px-6 pt-6 text-sm font-semibold text-ink-900">Members</h2>
            {actionError && (
              <p role="alert" className="px-6 pt-3 text-sm text-signal">
                {actionError}
              </p>
            )}
            {isLoading ? (
              <p className="px-6 py-6 text-sm text-ink-500">Loading…</p>
            ) : (
              <ul className="mt-4 divide-y divide-ink-100">
                {members.map((member) => (
                  <li key={member.id} className="flex items-center justify-between px-6 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-900">
                        {member.full_name ?? "Unnamed"}
                      </p>
                      <p className="truncate text-xs text-ink-500">{member.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <select
                        value={member.role.name}
                        onChange={(e) => handleRoleChange(member.id, e.target.value)}
                        className="rounded-md border border-ink-200 bg-white px-2 py-1.5 text-sm text-ink-900 focus:border-ink-500"
                      >
                        {roles.map((role) => (
                          <option key={role.id} value={role.name}>
                            {formatRoleName(role.name)}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => handleRemove(member.id)}
                        title="Remove member"
                        className="rounded-md p-1.5 text-ink-400 hover:bg-ink-50 hover:text-signal"
                      >
                        <UserMinus className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </main>
    </>
  );
}

function formatRoleName(name: string): string {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
