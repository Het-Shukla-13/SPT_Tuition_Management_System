import { useState } from "react";

import { SearchInput } from "@/components/shared/FilterBar";
import { Button } from "@/components/ui/button";
import { displayName } from "@/features/auth/session";
import type { AdminUser } from "@/lib/api/types";
import { formatPhone } from "@/lib/format";

import { usePortalLogins } from "../api";

/**
 * Find an existing parent/student login (e.g. a sibling's parent) by email,
 * phone or name, and pick it. `exclude` hides logins already chosen/linked.
 */
export function ExistingLoginPicker({
  onPick,
  exclude = [],
}: {
  onPick: (user: AdminUser) => void;
  exclude?: number[];
}) {
  const [search, setSearch] = useState("");
  const results = usePortalLogins(search);
  const rows = (results.data ?? []).filter((u) => !exclude.includes(u.id));

  return (
    <div className="flex flex-col gap-2">
      <SearchInput
        value={search}
        onChange={setSearch}
        label="Find an existing parent login"
        placeholder="Type an email, phone or name (2+ letters)"
      />
      {search.trim().length >= 2 && (
        <ul className="flex flex-col rounded-[var(--radius-control)] border border-line">
          {results.isPending && <li className="px-3 py-2.5 text-sm text-muted">Searching…</li>}
          {!results.isPending && rows.length === 0 && (
            <li className="px-3 py-2.5 text-sm text-muted">
              No parent login found. Add a new one instead.
            </li>
          )}
          {rows.map((u) => (
            <li
              key={u.id}
              className="flex items-center justify-between gap-3 border-t border-line/70 px-3 py-2 first:border-t-0"
            >
              <span className="flex min-w-0 flex-col">
                <span className="font-bold">{displayName(u)}</span>
                <span className="truncate text-xs text-muted">
                  {[u.email, u.phone && formatPhone(u.phone)].filter(Boolean).join(" · ")}
                </span>
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onPick(u);
                  setSearch("");
                }}
              >
                Link
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
