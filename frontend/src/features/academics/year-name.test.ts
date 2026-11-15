import { describe, expect, it } from "vitest";

import { checkYearName } from "./config";

describe("checkYearName", () => {
  it("accepts YYYY-YY that follows on and matches the start year", () => {
    expect(checkYearName("2026-27", { start_date: "2026-06-01" })).toBeUndefined();
    expect(checkYearName(" 2099-00 ", {})).toBeUndefined();
  });

  it("rejects other formats", () => {
    for (const name of ["2026-2027", "26-27", "2026/27", "bad"]) {
      expect(checkYearName(name, {})).toBe("Use the format YYYY-YY, e.g. 2026-27.");
    }
  });

  it("rejects years that don't follow on, or don't match the start date", () => {
    expect(checkYearName("2026-28", {})).toBe("The two years must follow on: 2026-27.");
    expect(checkYearName("2027-28", { start_date: "2026-04-01" })).toBe(
      "A year starting in 2026 should be called 2026-27.",
    );
  });
});
