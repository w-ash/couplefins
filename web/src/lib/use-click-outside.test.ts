import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useClickOutside } from "@/lib/use-click-outside";

function makeRef(el: HTMLElement | null = document.createElement("div")) {
  return { current: el };
}

describe("useClickOutside", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls onClose on mousedown outside ref element", () => {
    const onClose = vi.fn();
    const el = document.createElement("div");
    document.body.appendChild(el);
    const ref = makeRef(el);

    renderHook(() => useClickOutside(ref, true, onClose));

    // Click outside
    document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose on mousedown inside ref element", () => {
    const onClose = vi.fn();
    const el = document.createElement("div");
    const child = document.createElement("span");
    el.appendChild(child);
    document.body.appendChild(el);
    const ref = makeRef(el);

    renderHook(() => useClickOutside(ref, true, onClose));

    child.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose on Escape key", () => {
    const onClose = vi.fn();
    const ref = makeRef();

    renderHook(() => useClickOutside(ref, true, onClose));

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when active is false", () => {
    const onClose = vi.fn();
    const ref = makeRef();

    renderHook(() => useClickOutside(ref, false, onClose));

    document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("cleans up listeners on unmount", () => {
    const onClose = vi.fn();
    const ref = makeRef();

    const { unmount } = renderHook(() => useClickOutside(ref, true, onClose));
    unmount();

    document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("removes listeners when active changes to false", () => {
    const onClose = vi.fn();
    const ref = makeRef();

    const { rerender } = renderHook(
      ({ active }) => useClickOutside(ref, active, onClose),
      { initialProps: { active: true } },
    );

    rerender({ active: false });

    document.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    expect(onClose).not.toHaveBeenCalled();
  });
});
