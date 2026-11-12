import { keepPreviousData } from "@tanstack/react-query";
import { parseAsInteger, parseAsString, useQueryStates } from "nuqs";
import { useCallback, useMemo } from "react";

/**
 * The state of a list screen (page, search, filters) kept in the URL, so
 * Back/Forward work, a refresh keeps your place and a link can be shared.
 *
 *   const list = useListParams(["role", "is_active"]);
 *   list.params      -> { page, search, role, is_active } for the API call
 *   list.setFilter("role", "TEACHER")   (also resets to page 1)
 */
export function useListParams<K extends string>(
  filterKeys: readonly K[],
  defaults: Partial<Record<K, string>> = {},
) {
  // The filter keys are fixed per screen; this string keeps memos stable across renders.
  const keysId = filterKeys.join(",");
  const parsers = useMemo(() => {
    const map: Record<
      string,
      typeof parseAsString | ReturnType<typeof parseAsInteger.withDefault>
    > = {
      page: parseAsInteger.withDefault(1),
      search: parseAsString.withDefault(""),
    };
    for (const key of filterKeys) map[key] = parseAsString.withDefault(defaults[key] ?? "");
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keysId]);

  const [state, setState] = useQueryStates(parsers, { history: "replace" });
  const values = state as Record<string, string | number>;

  const filters = Object.fromEntries(filterKeys.map((k) => [k, String(values[k] ?? "")])) as Record<
    K,
    string
  >;
  const page = Number(values.page) || 1;
  const search = String(values.search ?? "");

  /** API query params: empty values left out. */
  const params: Record<string, string | number> = { page };
  if (search) params.search = search;
  for (const key of filterKeys) if (filters[key]) params[key] = filters[key];

  const setFilter = useCallback(
    (key: K, value: string) => void setState({ [key]: value || null, page: null } as never),
    [setState],
  );
  const setSearch = useCallback(
    (value: string) => void setState({ search: value || null, page: null } as never),
    [setState],
  );
  const setPage = useCallback(
    (value: number) => void setState({ page: value > 1 ? value : null } as never),
    [setState],
  );
  const clear = useCallback(
    () =>
      void setState(
        Object.fromEntries(["search", "page", ...filterKeys].map((k) => [k, null])) as never,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setState, keysId],
  );

  return { page, search, filters, params, setFilter, setSearch, setPage, clear };
}

/** Keep showing the previous page while the next one loads (no table flicker). */
export const listQueryOptions = { placeholderData: keepPreviousData } as const;
