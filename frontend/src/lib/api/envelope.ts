/**
 * The backend wraps every JSON response in one envelope (see
 * backend/docs/frontend/api-guide.md). These types describe it, and ApiError
 * is the single error type the whole app deals with.
 */

export type PageMeta = {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type Envelope<T> = {
  success: boolean;
  message: string;
  data: T;
  errors: unknown;
  error_code: string | null;
  meta: PageMeta | null;
};

/** Field errors of a VALIDATION_ERROR: `{ field: ["message", ...] }`. */
export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly errors: unknown;
  readonly requestId: string | null;

  constructor(opts: {
    status: number;
    code: string;
    message: string;
    errors?: unknown;
    requestId?: string | null;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.errors = opts.errors ?? null;
    this.requestId = opts.requestId ?? null;
  }

  /** Field → messages for form errors (empty unless VALIDATION_ERROR). */
  get fieldErrors(): FieldErrors {
    if (this.code !== "VALIDATION_ERROR" || !this.errors || typeof this.errors !== "object") {
      return {};
    }
    const out: FieldErrors = {};
    for (const [field, value] of Object.entries(this.errors as Record<string, unknown>)) {
      out[field] = Array.isArray(value) ? value.map(String) : [String(value)];
    }
    return out;
  }

  /** Seconds to wait, for 429 responses. */
  get retryAfterSeconds(): number | null {
    const value = (this.errors as { retry_after_seconds?: unknown } | null)?.retry_after_seconds;
    return typeof value === "number" ? value : null;
  }
}

export function isEnvelope(value: unknown): value is Envelope<unknown> {
  return (
    !!value &&
    typeof value === "object" &&
    "success" in value &&
    "error_code" in value &&
    "data" in value
  );
}
