/**
 * What each reference type looks like: its columns, form fields and filters.
 * The screens are generic (ReferenceSection / ReferenceForm); everything
 * type-specific lives here, so adding a field or a type is a config change.
 */
import type { ReactNode } from "react";

import { Badge } from "@/components/shared/StatusBadge";
import { formatDate } from "@/lib/format";

import type { ReferenceItem, ReferenceKey } from "./api";

export type FieldType = "text" | "number" | "date" | "select" | "checkbox";

export type FieldConfig = {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  hint?: string;
  /** select: the reference type whose active items are the options. */
  optionsFrom?: ReferenceKey;
  /** select: how to label one option. */
  optionLabel?: (item: ReferenceItem) => string;
  /** Can't be changed after creation (e.g. which board a year belongs to). */
  createOnly?: boolean;
  /** Narrow the full-width form grid: "half" fields sit side by side. */
  width?: "full" | "half";
};

export type ColumnConfig = {
  header: string;
  cell: (item: ReferenceItem) => ReactNode;
  align?: "right";
};

export type FilterConfig = {
  name: string;
  label: string;
  allLabel: string;
  optionsFrom: ReferenceKey;
  optionLabel?: (i: ReferenceItem) => string;
};

export type ReferenceConfig = {
  key: ReferenceKey;
  title: string;
  singular: string;
  description: string;
  searchable: boolean;
  searchPlaceholder?: string;
  ordering: string;
  filters: FilterConfig[];
  columns: ColumnConfig[];
  fields: FieldConfig[];
};

const s = (item: ReferenceItem, key: string) => String(item[key] ?? "–");
const boardLabel = (i: ReferenceItem) => `${s(i, "code")} · ${s(i, "name")}`;

const BOARD_FILTER: FilterConfig = {
  name: "board",
  label: "Board",
  allLabel: "All boards",
  optionsFrom: "boards",
  optionLabel: (i) => s(i, "code"),
};

export const REFERENCE_CONFIGS: ReferenceConfig[] = [
  {
    key: "academic-years",
    title: "Academic years",
    singular: "academic year",
    description:
      "Each board runs on its own dates. Enter the year's dates when the board announces them; mark one current year per board. Fees and admissions use the current year.",
    searchable: false,
    ordering: "-start_date",
    filters: [BOARD_FILTER],
    columns: [
      { header: "Board", cell: (i) => <b>{s(i, "board_code")}</b> },
      {
        header: "Year",
        cell: (i) => (
          <span className="flex items-center gap-2">
            {s(i, "name")}
            {Boolean(i.is_current) && <Badge tone="brand">Current</Badge>}
          </span>
        ),
      },
      { header: "Starts", cell: (i) => formatDate(i.start_date as string) },
      { header: "Ends", cell: (i) => formatDate(i.end_date as string) },
    ],
    fields: [
      {
        name: "board",
        label: "Board",
        type: "select",
        required: true,
        optionsFrom: "boards",
        optionLabel: boardLabel,
        createOnly: true,
      },
      { name: "name", label: "Name", type: "text", required: true, hint: "e.g. 2026-27" },
      { name: "start_date", label: "Starts on", type: "date", required: true, width: "half" },
      { name: "end_date", label: "Ends on", type: "date", required: true, width: "half" },
      {
        name: "is_current",
        label: "Current year for this board (replaces the previous current year)",
        type: "checkbox",
      },
    ],
  },
  {
    key: "boards",
    title: "Boards",
    singular: "board",
    description: "Education boards students study under.",
    searchable: true,
    searchPlaceholder: "Search name or code",
    ordering: "code",
    filters: [],
    columns: [
      { header: "Code", cell: (i) => <b>{s(i, "code")}</b> },
      { header: "Name", cell: (i) => s(i, "name") },
    ],
    fields: [
      {
        name: "code",
        label: "Code",
        type: "text",
        required: true,
        hint: "Short, e.g. CBSE",
        width: "half",
      },
      { name: "name", label: "Name", type: "text", required: true, width: "half" },
    ],
  },
  {
    key: "standards",
    title: "Standards",
    singular: "standard",
    description: "Classes taught at the institute.",
    searchable: false,
    ordering: "level",
    filters: [],
    columns: [
      { header: "Level", cell: (i) => <b className="tabular">{s(i, "level")}</b>, align: "right" },
      { header: "Name", cell: (i) => s(i, "name") },
    ],
    fields: [
      {
        name: "level",
        label: "Level",
        type: "number",
        required: true,
        hint: "1 to 12; sets the order",
        width: "half",
      },
      {
        name: "name",
        label: "Name",
        type: "text",
        required: true,
        hint: "e.g. Standard 10",
        width: "half",
      },
    ],
  },
  {
    key: "subjects",
    title: "Subjects",
    singular: "subject",
    description: "Subjects students can take.",
    searchable: true,
    searchPlaceholder: "Search name or code",
    ordering: "name",
    filters: [],
    columns: [
      { header: "Name", cell: (i) => <b>{s(i, "name")}</b> },
      { header: "Code", cell: (i) => s(i, "code") },
    ],
    fields: [
      { name: "name", label: "Name", type: "text", required: true, width: "half" },
      {
        name: "code",
        label: "Code",
        type: "text",
        required: true,
        hint: "e.g. MATH",
        width: "half",
      },
    ],
  },
  {
    key: "schools",
    title: "Schools",
    singular: "school",
    description: "Schools students come from. Used on admissions and to filter tests.",
    searchable: true,
    searchPlaceholder: "Search name or city",
    ordering: "name",
    filters: [BOARD_FILTER],
    columns: [
      { header: "School", cell: (i) => <b>{s(i, "name")}</b> },
      { header: "City", cell: (i) => s(i, "city") },
      { header: "Board", cell: (i) => s(i, "board_code") },
    ],
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "city", label: "City", type: "text", required: true, width: "half" },
      {
        name: "board",
        label: "Board (optional)",
        type: "select",
        optionsFrom: "boards",
        optionLabel: boardLabel,
        width: "half",
      },
    ],
  },
  {
    key: "chapters",
    title: "Chapters",
    singular: "chapter",
    description: "Chapters per board, standard and subject. Tests and notes are tagged with them.",
    searchable: true,
    searchPlaceholder: "Search chapter name",
    ordering: "number",
    filters: [
      BOARD_FILTER,
      {
        name: "standard",
        label: "Standard",
        allLabel: "All standards",
        optionsFrom: "standards",
        optionLabel: (i) => s(i, "name"),
      },
      {
        name: "subject",
        label: "Subject",
        allLabel: "All subjects",
        optionsFrom: "subjects",
        optionLabel: (i) => s(i, "name"),
      },
    ],
    columns: [
      { header: "No.", cell: (i) => <b className="tabular">{s(i, "number")}</b>, align: "right" },
      { header: "Chapter", cell: (i) => <b>{s(i, "name")}</b> },
      {
        header: "Class",
        cell: (i) => `${s(i, "board_code")} · ${s(i, "standard_name")} · ${s(i, "subject_name")}`,
      },
    ],
    fields: [
      {
        name: "board",
        label: "Board",
        type: "select",
        required: true,
        optionsFrom: "boards",
        optionLabel: boardLabel,
        width: "half",
      },
      {
        name: "standard",
        label: "Standard",
        type: "select",
        required: true,
        optionsFrom: "standards",
        optionLabel: (i) => s(i, "name"),
        width: "half",
      },
      {
        name: "subject",
        label: "Subject",
        type: "select",
        required: true,
        optionsFrom: "subjects",
        optionLabel: (i) => s(i, "name"),
        width: "half",
      },
      { name: "number", label: "Chapter no.", type: "number", required: true, width: "half" },
      { name: "name", label: "Chapter name", type: "text", required: true },
    ],
  },
];
