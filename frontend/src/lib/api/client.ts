/**
 * The ONE HTTP client of the app. Pages and components never call axios
 * directly: feature `api.ts` files use the helpers below.
 *
 * What it handles, so nothing else has to:
 * - adds the in-memory access token,
 * - sends cookies (the HttpOnly refresh token) and the CSRF header,
 * - unwraps the response envelope,
 * - turns every failure into an ApiError (network errors included),
 * - on 401: ONE shared refresh, then retries the call once; if the refresh
 *   fails, the session ends (the app shows the login page).
 */
import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

import { ApiError, type Envelope, isEnvelope, type PageMeta } from "./envelope";
import { session } from "./session";

export const API_BASE = "/api/v1/";
const REFRESH_PATH = "auth/token/refresh/";
const CSRF_HEADER = { "X-Requested-With": "XMLHttpRequest" };

// Login-type calls: a 401 there is a form error ("wrong code"), never "token expired".
const NO_REFRESH_PATHS = [
  REFRESH_PATH,
  "auth/login/",
  "auth/password/reset/",
  "auth/otp/",
  "auth/google/",
];

const common = {
  baseURL: API_BASE,
  withCredentials: true,
  headers: { Accept: "application/json", ...CSRF_HEADER },
  timeout: 30_000,
};

export const http = axios.create(common);
/** No interceptors: used for the refresh call itself. */
const bare = axios.create(common);

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof AxiosError) {
    const requestId = (error.response?.headers?.["x-request-id"] as string | undefined) ?? null;
    const body = error.response?.data;
    if (error.response && isEnvelope(body)) {
      return new ApiError({
        status: error.response.status,
        code: body.error_code ?? "ERROR",
        message: body.message,
        errors: body.errors,
        requestId,
      });
    }
    if (error.response) {
      return new ApiError({
        status: error.response.status,
        code: "UNEXPECTED_RESPONSE",
        message: "The server sent an unexpected response. Please try again.",
        requestId,
      });
    }
    return new ApiError({
      status: 0,
      code: "NETWORK_ERROR",
      message: "Can't reach the server. Check your internet connection and try again.",
    });
  }
  return new ApiError({ status: 0, code: "CLIENT_ERROR", message: String(error) });
}

// ── The single shared refresh ────────────────────────────────────────────
let refreshing: Promise<string> | null = null;

/**
 * Get a new access token from the refresh cookie. Concurrent callers share
 * one request: refresh tokens rotate, so two parallel refreshes would race.
 */
export function refreshAccessToken(): Promise<string> {
  refreshing ??= bare
    .post<Envelope<{ access: string }>>(REFRESH_PATH, {})
    .then((response) => {
      const token = response.data.data.access;
      session.setAccessToken(token);
      return token;
    })
    .catch((error: unknown) => {
      const apiError = toApiError(error);
      // Only an auth failure ends the session; a network blip doesn't.
      if (apiError.status === 401 || apiError.status === 403) session.clear(apiError.code);
      throw apiError;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

http.interceptors.request.use((config) => {
  const token = session.getAccessToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

http.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!(error instanceof AxiosError) || !error.config) throw toApiError(error);
    const config = error.config as RetriableConfig;
    const url = config.url ?? "";
    const expired =
      error.response?.status === 401 &&
      !config._retried &&
      !NO_REFRESH_PATHS.some((path) => url.startsWith(path));
    if (!expired) throw toApiError(error);

    config._retried = true;
    await refreshAccessToken(); // throws ApiError (and ends the session) on failure
    return http(config);
  },
);

// ── Helpers used by feature api.ts files ─────────────────────────────────
export type Page<T> = { items: T; meta: PageMeta };

async function call<T>(config: AxiosRequestConfig): Promise<Envelope<T>> {
  const response = await http.request<Envelope<T>>(config);
  return response.data;
}

export const api = {
  async get<T>(url: string, params?: object): Promise<T> {
    return (await call<T>({ method: "GET", url, params })).data;
  },
  /** For paginated lists: the rows plus the page metadata. */
  async list<T>(url: string, params?: object): Promise<Page<T[]>> {
    const body = await call<T[]>({ method: "GET", url, params });
    return {
      items: body.data,
      meta: body.meta ?? {
        page: 1,
        page_size: body.data.length,
        total_count: body.data.length,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
    };
  },
  async post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return (await call<T>({ method: "POST", url, data, ...config })).data;
  },
  async patch<T>(url: string, data?: unknown): Promise<T> {
    return (await call<T>({ method: "PATCH", url, data })).data;
  },
  async delete<T>(url: string): Promise<T> {
    return (await call<T>({ method: "DELETE", url })).data;
  },
  /** File downloads: the bytes plus the server's file name. */
  async download(url: string, params?: object): Promise<{ blob: Blob; filename: string | null }> {
    const response = await http.get<Blob>(url, { params, responseType: "blob" });
    const disposition = (response.headers["content-disposition"] as string | undefined) ?? "";
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
    return { blob: response.data, filename: match?.[1] ? decodeURIComponent(match[1]) : null };
  },
};
