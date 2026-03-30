import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useMutationTimeout } from "./useMutationTimeout";

describe("useMutationTimeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns idle state when not pending", () => {
    const { result } = renderHook(() => useMutationTimeout(false));

    expect(result.current.timedOut).toBe(false);
    expect(result.current.slowHint).toBeNull();
  });

  it("returns idle state initially when pending", () => {
    const { result } = renderHook(() => useMutationTimeout(true));

    expect(result.current.timedOut).toBe(false);
    expect(result.current.slowHint).toBeNull();
  });

  it("shows slowHint after 5 seconds of pending", () => {
    const { result } = renderHook(() => useMutationTimeout(true));

    act(() => vi.advanceTimersByTime(5_000));

    expect(result.current.slowHint).toBe(
      "Taking longer than usual \u2014 the database may need a moment to wake up",
    );
    expect(result.current.timedOut).toBe(false);
  });

  it("sets timedOut after 30 seconds and hides slowHint", () => {
    const { result } = renderHook(() => useMutationTimeout(true));

    act(() => vi.advanceTimersByTime(30_000));

    expect(result.current.timedOut).toBe(true);
    expect(result.current.slowHint).toBeNull();
  });

  it("resets when isPending becomes false", () => {
    const { result, rerender } = renderHook(
      ({ pending }) => useMutationTimeout(pending),
      { initialProps: { pending: true } },
    );

    act(() => vi.advanceTimersByTime(10_000));
    expect(result.current.slowHint).not.toBeNull();

    rerender({ pending: false });
    expect(result.current.timedOut).toBe(false);
    expect(result.current.slowHint).toBeNull();
  });

  it("reset() clears both states", () => {
    const { result } = renderHook(() => useMutationTimeout(true));

    act(() => vi.advanceTimersByTime(30_000));
    expect(result.current.timedOut).toBe(true);

    act(() => result.current.reset());
    expect(result.current.timedOut).toBe(false);
    expect(result.current.slowHint).toBeNull();
  });

  it("accepts custom timing options", () => {
    const { result } = renderHook(() =>
      useMutationTimeout(true, {
        slowMs: 2_000,
        timeoutMs: 10_000,
        slowHint: "Custom hint",
      }),
    );

    act(() => vi.advanceTimersByTime(2_000));
    expect(result.current.slowHint).toBe("Custom hint");

    act(() => vi.advanceTimersByTime(8_000));
    expect(result.current.timedOut).toBe(true);
  });
});
