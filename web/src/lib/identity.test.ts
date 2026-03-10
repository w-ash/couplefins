import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "./identity";

const STORAGE_KEY = "couplefins:currentPersonId";

describe("identity store", () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    useIdentityStore.setState({ currentPersonId: null });
  });

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY);
  });

  it("starts with null currentPersonId", () => {
    expect(useIdentityStore.getState().currentPersonId).toBeNull();
  });

  it("sets currentPersonId", () => {
    useIdentityStore.getState().setCurrentPersonId("abc-123");
    expect(useIdentityStore.getState().currentPersonId).toBe("abc-123");
  });

  it("clears identity", () => {
    useIdentityStore.getState().setCurrentPersonId("abc-123");
    useIdentityStore.getState().clearIdentity();
    expect(useIdentityStore.getState().currentPersonId).toBeNull();
  });

  it("persists currentPersonId to localStorage", () => {
    useIdentityStore.getState().setCurrentPersonId("abc-123");
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.state.currentPersonId).toBe("abc-123");
  });

  it("hydrates from localStorage", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ state: { currentPersonId: "xyz-789" }, version: 0 }),
    );
    await useIdentityStore.persist.rehydrate();
    expect(useIdentityStore.getState().currentPersonId).toBe("xyz-789");
  });

  it("reports hydrated via persist API", () => {
    expect(useIdentityStore.persist.hasHydrated()).toBe(true);
  });
});
