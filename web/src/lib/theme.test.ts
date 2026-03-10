import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyTheme, getStoredTheme, resolveIsDark, storeTheme } from "./theme";

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("getStoredTheme", () => {
  beforeEach(() => {
    window.localStorage.removeItem("couplefins:theme");
  });

  it("returns 'system' when localStorage is empty", () => {
    expect(getStoredTheme()).toBe("system");
  });

  it("returns stored valid value", () => {
    window.localStorage.setItem("couplefins:theme", "dark");
    expect(getStoredTheme()).toBe("dark");
  });

  it("returns 'system' for invalid stored value", () => {
    window.localStorage.setItem("couplefins:theme", "invalid");
    expect(getStoredTheme()).toBe("system");
  });

  it("returns 'system' when localStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getStoredTheme()).toBe("system");
    vi.restoreAllMocks();
  });
});

describe("storeTheme", () => {
  beforeEach(() => {
    window.localStorage.removeItem("couplefins:theme");
  });

  it("writes to localStorage", () => {
    storeTheme("dark");
    expect(window.localStorage.getItem("couplefins:theme")).toBe("dark");
  });

  it("does not throw when localStorage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => storeTheme("dark")).not.toThrow();
    vi.restoreAllMocks();
  });
});

describe("resolveIsDark", () => {
  it("returns true for 'dark'", () => {
    expect(resolveIsDark("dark")).toBe(true);
  });

  it("returns false for 'light'", () => {
    expect(resolveIsDark("light")).toBe(false);
  });

  it("follows matchMedia for 'system' (dark)", () => {
    mockMatchMedia(true);
    expect(resolveIsDark("system")).toBe(true);
  });

  it("follows matchMedia for 'system' (light)", () => {
    mockMatchMedia(false);
    expect(resolveIsDark("system")).toBe(false);
  });
});

describe("applyTheme", () => {
  afterEach(() => {
    document.documentElement.classList.remove("dark");
  });

  it("adds .dark class for dark theme", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes .dark class for light theme", () => {
    document.documentElement.classList.add("dark");
    applyTheme("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("adds .dark class for system when OS prefers dark", () => {
    mockMatchMedia(true);
    applyTheme("system");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("removes .dark class for system when OS prefers light", () => {
    mockMatchMedia(false);
    document.documentElement.classList.add("dark");
    applyTheme("system");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
