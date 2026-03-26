import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "./identity";

describe("identity store", () => {
  beforeEach(() => {
    useIdentityStore.setState({
      currentPersonId: null,
      currentPersonName: null,
    });
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
    expect(useIdentityStore.getState().currentPersonName).toBeNull();
  });

  it("sets from auth response", () => {
    useIdentityStore
      .getState()
      .setFromAuthResponse({ id: "abc-123", name: "Alice" });
    expect(useIdentityStore.getState().currentPersonId).toBe("abc-123");
    expect(useIdentityStore.getState().currentPersonName).toBe("Alice");
  });

  it("does not persist to localStorage", () => {
    useIdentityStore.getState().setCurrentPersonId("abc-123");
    const stored = localStorage.getItem("couplefins:currentPersonId");
    expect(stored).toBeNull();
  });
});
