import { useState } from "react";
import { Link } from "react-router";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { ActiveFilters, FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge, StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { displayName, ROLE_LABEL } from "@/features/auth/session";
import type { AdminUser } from "@/lib/api/types";
import { formatAgo, formatPhone } from "@/lib/format";
import { useListParams } from "@/lib/useListParams";

import { ROLE_OPTIONS, userStatus, useUsers } from "../api";
import { InviteUserDialog } from "../components/InviteUserDialog";

const FILTER_KEYS = ["role", "is_active"] as const;
const STATUS_OPTIONS = [
  { value: "true", label: "Active" },
  { value: "false", label: "Deactivated" },
];

const columns: ColumnDef<AdminUser, unknown>[] = [
  {
    header: "Name",
    id: "name",
    cell: ({ row }) => (
      <Link
        to={`/staff/users/${row.original.id}`}
        className="font-bold text-ink hover:text-primary hover:underline"
      >
        {displayName(row.original)}
        {row.original.is_superuser && (
          <Badge tone="brand" className="ml-2">
            Owner
          </Badge>
        )}
      </Link>
    ),
  },
  {
    header: "Role",
    id: "role",
    cell: ({ row }) => (
      <Badge tone={row.original.role === "PORTAL" ? "info" : "neutral"}>
        {ROLE_LABEL[row.original.role]}
      </Badge>
    ),
  },
  {
    header: "Login",
    id: "login",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.email ?? "–"}</span>
        {row.original.phone && (
          <span className="text-xs text-muted">{formatPhone(row.original.phone)}</span>
        )}
      </span>
    ),
  },
  {
    header: "Status",
    id: "status",
    cell: ({ row }) => <StatusBadge status={userStatus(row.original)} />,
  },
  {
    header: "Last login",
    id: "last_login",
    cell: ({ row }) => (
      <span className="text-muted">
        {row.original.last_login ? formatAgo(row.original.last_login) : "Never"}
      </span>
    ),
  },
];

/** Everyone who can log in. Staff are invited here; parents come from admissions. */
export function UsersPage() {
  const list = useListParams(FILTER_KEYS, { is_active: "true" });
  const users = useUsers(list.params);
  const [inviting, setInviting] = useState(false);

  const active = [
    ...(list.filters.role
      ? [
          {
            key: "role",
            label:
              ROLE_OPTIONS.find((r) => r.value === list.filters.role)?.label ?? list.filters.role,
            onRemove: () => list.setFilter("role", ""),
          },
        ]
      : []),
    ...(list.search
      ? [{ key: "search", label: `“${list.search}”`, onRemove: () => list.setSearch("") }]
      : []),
  ];

  return (
    <>
      <PageHeader
        title="Users & invites"
        eyebrow="Everyone who can log in. Parents are added from the admission form."
        actions={<Button onClick={() => setInviting(true)}>+ Invite staff</Button>}
      />
      <div className="flex flex-col gap-3">
        <FilterBar>
          <SearchInput
            value={list.search}
            onChange={list.setSearch}
            placeholder="Search email or phone"
          />
          <FilterSelect
            label="Role"
            allLabel="All roles"
            value={list.filters.role}
            onChange={(v) => list.setFilter("role", v)}
            options={ROLE_OPTIONS}
          />
          <FilterSelect
            label="Status"
            allLabel="Any status"
            value={list.filters.is_active}
            onChange={(v) => list.setFilter("is_active", v)}
            options={STATUS_OPTIONS}
          />
        </FilterBar>
        <ActiveFilters items={active} onClearAll={list.clear} />
      </div>
      <DataTable
        caption="Users"
        columns={columns}
        rows={users.data?.items}
        meta={users.data?.meta}
        loading={users.isFetching && !users.data}
        error={users.error}
        onRetry={() => void users.refetch()}
        onPageChange={list.setPage}
        rowKey={(u) => u.id}
        empty={{ title: "No users match", description: "Try another role or clear the search." }}
      />
      <InviteUserDialog open={inviting} onOpenChange={setInviting} />
    </>
  );
}
