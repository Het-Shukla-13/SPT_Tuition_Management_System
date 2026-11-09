import { http as mock, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";

import { api } from "./client";
import { ApiError } from "./envelope";
import { session } from "./session";

const BASE = `${window.location.origin}/api/v1`;
const ok = <T>(data: T, meta: unknown = null) =>
  HttpResponse.json({ success: true, message: "OK", data, errors: null, error_code: null, meta });
const fail = (status: number, code: string, errors: unknown = null) =>
  HttpResponse.json(
    {
      success: false,
      message: `failed: ${code}`,
      data: null,
      errors,
      error_code: code,
      meta: null,
    },
    { status, headers: { "X-Request-ID": "req-123" } },
  );

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => session.setAccessToken("old-access"));

describe("api client", () => {
  it("sends the access token and the CSRF header, and unwraps data", async () => {
    let seen: Headers | undefined;
    server.use(
      mock.get(`${BASE}/auth/me/`, ({ request }) => {
        seen = request.headers;
        return ok({ id: 1 });
      }),
    );
    await expect(api.get("auth/me/")).resolves.toEqual({ id: 1 });
    expect(seen?.get("authorization")).toBe("Bearer old-access");
    expect(seen?.get("x-requested-with")).toBe("XMLHttpRequest");
  });

  it("on 401: refreshes ONCE for parallel calls, then retries each with the new token", async () => {
    let refreshes = 0;
    server.use(
      mock.post(`${BASE}/auth/token/refresh/`, () => {
        refreshes += 1;
        return ok({ access: "new-access" });
      }),
      mock.get(`${BASE}/thing/:n/`, ({ request, params }) =>
        request.headers.get("authorization") === "Bearer new-access"
          ? ok({ n: params.n })
          : fail(401, "TOKEN_NOT_VALID"),
      ),
    );
    const results = await Promise.all([1, 2, 3].map((n) => api.get(`thing/${n}/`)));
    expect(results).toEqual([{ n: "1" }, { n: "2" }, { n: "3" }]);
    expect(refreshes).toBe(1);
    expect(session.getAccessToken()).toBe("new-access");
  });

  it("ends the session when the refresh fails", async () => {
    server.use(
      mock.post(`${BASE}/auth/token/refresh/`, () => fail(401, "SESSION_EXPIRED")),
      mock.get(`${BASE}/thing/`, () => fail(401, "TOKEN_NOT_VALID")),
    );
    await expect(api.get("thing/")).rejects.toMatchObject({ code: "SESSION_EXPIRED" });
    expect(session.getAccessToken()).toBeNull();
    expect(session.getEndedReason()).toBe("SESSION_EXPIRED");
  });

  it("never refreshes for a wrong OTP (401 there means 'wrong code')", async () => {
    let refreshes = 0;
    server.use(
      mock.post(`${BASE}/auth/token/refresh/`, () => {
        refreshes += 1;
        return ok({ access: "x" });
      }),
      mock.post(`${BASE}/auth/otp/verify/`, () => fail(401, "OTP_INVALID")),
    );
    await expect(api.post("auth/otp/verify/", {})).rejects.toMatchObject({ code: "OTP_INVALID" });
    expect(refreshes).toBe(0);
  });

  it("turns error envelopes into ApiError with field errors and request id", async () => {
    server.use(
      mock.post(`${BASE}/students/`, () =>
        fail(400, "VALIDATION_ERROR", { first_name: ["This field is required."] }),
      ),
    );
    const error = await api.post("students/", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(400);
    expect(apiError.fieldErrors).toEqual({ first_name: ["This field is required."] });
    expect(apiError.requestId).toBe("req-123");
  });

  it("reports a dropped connection as NETWORK_ERROR (and keeps the session)", async () => {
    server.use(mock.get(`${BASE}/thing/`, () => HttpResponse.error()));
    await expect(api.get("thing/")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
    expect(session.getAccessToken()).toBe("old-access");
  });

  it("list() returns rows plus pagination meta", async () => {
    const meta = {
      page: 2,
      page_size: 20,
      total_count: 41,
      total_pages: 3,
      has_next: true,
      has_previous: true,
    };
    server.use(mock.get(`${BASE}/admin/students/`, () => ok([{ id: 1 }], meta)));
    await expect(api.list("admin/students/", { page: 2 })).resolves.toEqual({
      items: [{ id: 1 }],
      meta,
    });
  });
});
