import { describe, expect, it } from "vitest";
import {
  CURRENCY_EPSILON,
  computeShares,
  formatMonthSpan,
  formatSignedCurrency,
  isZeroCurrency,
} from "./format";

describe("isZeroCurrency", () => {
  it("treats exact zero and negative zero as zero", () => {
    expect(isZeroCurrency(0)).toBe(true);
    expect(isZeroCurrency(-0)).toBe(true);
  });

  it("treats sub-half-cent amounts as zero, either sign", () => {
    expect(isZeroCurrency(0.004)).toBe(true);
    expect(isZeroCurrency(-0.004)).toBe(true);
  });

  it("collapses float dust from summing signed amounts", () => {
    expect(isZeroCurrency(-5.551115123125783e-17)).toBe(true);
  });

  it("is exclusive at the half-cent boundary", () => {
    expect(isZeroCurrency(CURRENCY_EPSILON)).toBe(false);
    expect(isZeroCurrency(-CURRENCY_EPSILON)).toBe(false);
    expect(isZeroCurrency(0.006)).toBe(false);
  });
});

describe("formatSignedCurrency", () => {
  it("renders near-zero amounts as unsigned $0.00", () => {
    expect(formatSignedCurrency(0)).toBe("$0.00");
    expect(formatSignedCurrency(-0.004)).toBe("$0.00");
    expect(formatSignedCurrency(-5.551115123125783e-17)).toBe("$0.00");
  });

  it("prefixes positive amounts with +", () => {
    expect(formatSignedCurrency(50)).toBe("+$50.00");
    expect(formatSignedCurrency(1234.5)).toBe("+$1,234.50");
  });

  it("prefixes negative amounts with a true minus sign (U+2212)", () => {
    expect(formatSignedCurrency(-50)).toBe("−$50.00");
    expect(formatSignedCurrency(-73.4)).toBe("−$73.40");
  });
});

describe("formatMonthSpan", () => {
  it("names a single month in full", () => {
    expect(
      formatMonthSpan({
        start: { year: 2026, month: 3 },
        end: { year: 2026, month: 3 },
      }),
    ).toBe("March");
  });

  it("abbreviates a same-year span with an en dash", () => {
    expect(
      formatMonthSpan({
        start: { year: 2026, month: 3 },
        end: { year: 2026, month: 5 },
      }),
    ).toBe("Mar–May");
  });

  it("includes years when the span crosses a year boundary", () => {
    expect(
      formatMonthSpan({
        start: { year: 2025, month: 11 },
        end: { year: 2026, month: 2 },
      }),
    ).toBe("Nov 2025 – Feb 2026");
  });
});

describe("computeShares", () => {
  it("uses complementary rounding matching the backend (4.15 at 50%)", () => {
    // Backend: payer 2.075 → ROUND_HALF_UP 2.08; other = 4.15 − 2.08 = 2.07
    expect(computeShares(4.15, 50)).toEqual({
      payerShare: 2.08,
      otherShare: 2.07,
    });
  });

  it("shares always sum to the transaction amount", () => {
    const cases: [number, number][] = [
      [4.15, 50],
      [0.01, 50],
      [99.99, 33],
      [10.05, 70],
      [123.45, 1],
    ];
    for (const [amount, pct] of cases) {
      const { payerShare, otherShare } = computeShares(amount, pct);
      expect(payerShare + otherShare).toBeCloseTo(amount, 10);
    }
  });

  it("gives the rounding cent to the payer at half-cent splits", () => {
    expect(computeShares(0.01, 50)).toEqual({
      payerShare: 0.01,
      otherShare: 0,
    });
  });
});
