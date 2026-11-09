import { describe, expect, it } from "vitest";

import { formatMarks, formatMoney, formatPhone, initials } from "./format";

describe("formatMoney", () => {
  it("formats API money strings the Indian way", () => {
    expect(formatMoney("26000.00")).toBe("₹26,000");
    expect(formatMoney("142500")).toBe("₹1,42,500");
    expect(formatMoney("1234.50")).toBe("₹1,234.5");
  });
  it("shows a dash for missing or broken values", () => {
    expect(formatMoney(null)).toBe("–");
    expect(formatMoney("")).toBe("–");
    expect(formatMoney("abc")).toBe("–");
  });
});

describe("formatMarks", () => {
  it("drops useless decimals", () => {
    expect(formatMarks("21.50")).toBe("21.5");
    expect(formatMarks("25.00")).toBe("25");
    expect(formatMarks(null)).toBe("–");
  });
});

describe("formatPhone / initials", () => {
  it("groups Indian mobile numbers", () => {
    expect(formatPhone("+919876543210")).toBe("+91 98765 43210");
    expect(formatPhone("+14155550100")).toBe("+14155550100");
  });
  it("takes first and last initials", () => {
    expect(initials("Kavita Shah")).toBe("KS");
    expect(initials("Kavita Ben Shah")).toBe("KS");
    expect(initials("  ")).toBe("?");
  });
});
