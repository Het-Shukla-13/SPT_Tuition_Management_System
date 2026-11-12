import { useMemo, useState } from "react";
import { toast } from "sonner";

import { type ColumnDef, DataTable } from "@/components/shared/DataTable";
import { FilterBar, FilterSelect, SearchInput } from "@/components/shared/FilterBar";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/envelope";
import { useListParams } from "@/lib/useListParams";

import {
  type ReferenceItem,
  useReferenceList,
  useReferenceOptions,
  useSaveReference,
} from "../api";
import type { FilterConfig, ReferenceConfig } from "../config";
import { ReferenceForm } from "./ReferenceForm";

const STATUS_OPTIONS = [
  { value: "true", label: "Active" },
  { value: "false", label: "Deactivated" },
];

/**
 * One reference type's screen: filters, the table, add/edit, and
 * deactivate/reactivate. Used for all six types (see config.tsx).
 */
export function ReferenceSection({ config }: { config: ReferenceConfig }) {
  const filterKeys = useMemo(() => [...config.filters.map((f) => f.name), "is_active"], [config]);
  const list = useListParams(filterKeys, { is_active: "true" });
  const items = useReferenceList(config.key, { ...list.params, ordering: config.ordering });
  const save = useSaveReference(config.key);
  const [editing, setEditing] = useState<ReferenceItem | null | undefined>(undefined);

  const toggleActive = (item: ReferenceItem) =>
    save.mutate(
      { id: item.id, body: { is_active: !item.is_active } },
      {
        onSuccess: () =>
          toast.success(
            item.is_active
              ? "Deactivated. It's hidden from forms; history keeps it."
              : "Reactivated.",
          ),
        onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't change it."),
      },
    );

  const columns: ColumnDef<ReferenceItem, unknown>[] = [
    ...config.columns.map((c, index): ColumnDef<ReferenceItem, unknown> => ({
      id: `c${index}`,
      header: c.header,
      meta: c.align ? { align: c.align } : undefined,
      cell: ({ row }) => c.cell(row.original),
    })),
    {
      id: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.is_active ? "ACTIVE" : "INACTIVE"} />,
    },
    {
      id: "actions",
      header: "",
      meta: { align: "right" },
      cell: ({ row }) => (
        <span className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => setEditing(row.original)}>
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={save.isPending}
            onClick={() => toggleActive(row.original)}
          >
            {row.original.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        </span>
      ),
    },
  ];

  return (
    <section className="flex flex-col gap-4" aria-label={config.title}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">{config.description}</p>
        <Button onClick={() => setEditing(null)}>+ Add {config.singular}</Button>
      </div>
      <FilterBar>
        {config.searchable && (
          <SearchInput
            value={list.search}
            onChange={list.setSearch}
            placeholder={config.searchPlaceholder ?? "Search"}
          />
        )}
        {config.filters.map((filter) => (
          <ReferenceFilter
            key={filter.name}
            filter={filter}
            value={list.filters[filter.name] ?? ""}
            onChange={(v) => list.setFilter(filter.name, v)}
          />
        ))}
        <FilterSelect
          label="Status"
          allLabel="Any status"
          value={list.filters.is_active ?? ""}
          onChange={(v) => list.setFilter("is_active", v)}
          options={STATUS_OPTIONS}
        />
      </FilterBar>
      <DataTable
        caption={config.title}
        columns={columns}
        rows={items.data?.items}
        meta={items.data?.meta}
        loading={items.isFetching && !items.data}
        error={items.error}
        onRetry={() => void items.refetch()}
        onPageChange={list.setPage}
        rowKey={(i) => i.id}
        empty={{
          title: `No ${config.title.toLowerCase()} here`,
          description: "Change the filters, or add one.",
          action: <Button onClick={() => setEditing(null)}>+ Add {config.singular}</Button>,
        }}
      />
      {editing !== undefined && (
        <ReferenceForm
          key={editing?.id ?? "new"}
          config={config}
          item={editing}
          open
          onOpenChange={(open) => !open && setEditing(undefined)}
        />
      )}
    </section>
  );
}

function ReferenceFilter({
  filter,
  value,
  onChange,
}: {
  filter: FilterConfig;
  value: string;
  onChange: (v: string) => void;
}) {
  const options = useReferenceOptions(filter.optionsFrom);
  return (
    <FilterSelect
      label={filter.label}
      allLabel={filter.allLabel}
      value={value}
      onChange={onChange}
      options={(options.data ?? []).map((o) => ({
        value: String(o.id),
        label: filter.optionLabel ? filter.optionLabel(o) : String(o.name ?? o.id),
      }))}
    />
  );
}
