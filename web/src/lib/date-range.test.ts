import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  formatRangeLabel,
  isSingleMonth,
  lastMonth,
  lastYear,
  parseDate,
  thisMonth,
  toDateStr,
  yearToDate,
} from "./date-range";

describe("isSingleMonth", () => {
  it("recognizes a full month", () => {
    expect(isSingleMonth("2026-03-01", "2026-03-31")).toEqual({
      year: 2026,
      month: 3,
    });
  });

  it("recognizes February 28 in a non-leap year", () => {
    expect(isSingleMonth("2025-02-01", "2025-02-28")).toEqual({
      year: 2025,
      month: 2,
    });
  });

  it("recognizes February 29 in a leap year", () => {
    expect(isSingleMonth("2024-02-01", "2024-02-29")).toEqual({
      year: 2024,
      month: 2,
    });
  });

  it("rejects a partial month (start not day 1)", () => {
    expect(isSingleMonth("2026-03-05", "2026-03-31")).toBeNull();
  });

  it("rejects a partial month (end before last day)", () => {
    expect(isSingleMonth("2026-03-01", "2026-03-15")).toBeNull();
  });

  it("rejects a cross-month range", () => {
    expect(isSingleMonth("2026-01-01", "2026-02-28")).toBeNull();
  });
});

describe("formatRangeLabel", () => {
  it("formats a single month as 'Month Year'", () => {
    expect(formatRangeLabel("2026-03-01", "2026-03-31")).toBe("March 2026");
  });

  it("formats January", () => {
    expect(formatRangeLabel("2026-01-01", "2026-01-31")).toBe("January 2026");
  });

  it("formats a custom range with short dates", () => {
    const label = formatRangeLabel("2026-01-01", "2026-03-13");
    expect(label).toContain("Jan");
    expect(label).toContain("2026");
    expect(label).toContain("\u2013");
    expect(label).toContain("Mar");
  });
});

describe("presets", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 2, 13)); // March 13, 2026
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("thisMonth returns full current month", () => {
    const range = thisMonth();
    expect(range.startDate).toBe("2026-03-01");
    expect(range.endDate).toBe("2026-03-31");
  });

  it("lastMonth returns full previous month", () => {
    const range = lastMonth();
    expect(range.startDate).toBe("2026-02-01");
    expect(range.endDate).toBe("2026-02-28");
  });

  it("yearToDate returns Jan 1 through today", () => {
    const range = yearToDate();
    expect(range.startDate).toBe("2026-01-01");
    expect(range.endDate).toBe("2026-03-13");
  });

  it("lastYear returns full previous year", () => {
    const range = lastYear();
    expect(range.startDate).toBe("2025-01-01");
    expect(range.endDate).toBe("2025-12-31");
  });
});

describe("toDateStr / parseDate", () => {
  it("round-trips a date", () => {
    const str = "2026-03-13";
    expect(toDateStr(parseDate(str))).toBe(str);
  });

  it("zero-pads single-digit months and days", () => {
    const d = new Date(2026, 0, 5); // Jan 5
    expect(toDateStr(d)).toBe("2026-01-05");
  });

  it("parseDate creates a local midnight date", () => {
    const d = parseDate("2026-07-04");
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(6); // 0-indexed
    expect(d.getDate()).toBe(4);
    expect(d.getHours()).toBe(0);
  });
});
