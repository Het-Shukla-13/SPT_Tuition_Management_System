import { type ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import type { PageMeta } from "@/lib/api/envelope";
import { cn } from "@/lib/utils";

import { EmptyState, ErrorState } from "./States";

export type { ColumnDef };

/**
 * The one list component for the whole app (students, fees, payments, users,
 * tests, assignments...): give it columns and rows; it draws loading, empty,
 * error and pagination the same way everywhere.
 *
 * It's "controlled": the page owns page/filter state (kept in the URL), and
 * the server does the sorting, filtering and paging.
 */
export function DataTable<T>({
  columns,
  rows,
  meta,
  loading,
  error,
  onRetry,
  onPageChange,
  empty,
  rowKey,
  caption,
}: {
  columns: ColumnDef<T, unknown>[];
  rows: T[] | undefined;
  meta?: PageMeta | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onPageChange?: (page: number) => void;
  empty?: { title: string; description?: ReactNode; action?: ReactNode };
  rowKey?: (row: T) => string | number;
  /** Screen-reader description of the table. */
  caption: string;
}) {
  // TanStack Table manages its own memoisation; it isn't React Compiler-safe (known, harmless here).
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: rows ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    getRowId: rowKey ? (row) => String(rowKey(row)) : undefined,
  });

  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!loading && rows && rows.length === 0) {
    return <EmptyState title={empty?.title ?? "Nothing here yet"} {...empty} />;
  }

  return (
    <div className="flex flex-col gap-3">
      <Table aria-busy={loading || undefined}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <Th
                  key={header.id}
                  className={cn(
                    (header.column.columnDef.meta as ColumnMeta | undefined)?.align === "right" &&
                      "text-right",
                  )}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </Th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {loading && !rows
            ? Array.from({ length: 6 }, (_, i) => (
                <tr key={`skeleton-${i}`}>
                  {columns.map((_, j) => (
                    <Td key={j}>
                      <Skeleton className="h-4 w-24" />
                    </Td>
                  ))}
                </tr>
              ))
            : table.getRowModel().rows.map((row) => (
                <Tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <Td
                      key={cell.id}
                      className={cn(
                        (cell.column.columnDef.meta as ColumnMeta | undefined)?.align === "right" &&
                          "tabular text-right",
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </Td>
                  ))}
                </Tr>
              ))}
        </tbody>
      </Table>
      {meta && onPageChange && <Pagination meta={meta} onPageChange={onPageChange} />}
    </div>
  );
}

/** Per-column options: `meta: { align: "right" }` for money and marks. */
export type ColumnMeta = { align?: "right" };

export function Pagination({
  meta,
  onPageChange,
}: {
  meta: PageMeta;
  onPageChange: (page: number) => void;
}) {
  if (meta.total_count === 0) return null;
  const first = (meta.page - 1) * meta.page_size + 1;
  const last = Math.min(meta.page * meta.page_size, meta.total_count);
  return (
    <nav
      aria-label="Pages"
      className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted"
    >
      <span className="tabular">
        Showing {first}–{last} of {meta.total_count}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={!meta.has_previous}
          onClick={() => onPageChange(meta.page - 1)}
        >
          <ChevronLeftIcon aria-hidden="true" /> Previous
        </Button>
        <span className="tabular px-1 font-bold text-ink">
          {meta.page} / {meta.total_pages}
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={!meta.has_next}
          onClick={() => onPageChange(meta.page + 1)}
        >
          Next <ChevronRightIcon aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
