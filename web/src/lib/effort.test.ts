import { beforeEach, describe, expect, it } from "vitest";
import { EFFORT_API_VALUES, getStoredEffort, storeEffort } from "./effort";

describe("effort storage", () => {
  beforeEach(() => {
    window.localStorage.removeItem("couplefins:chatEffort");
  });

  it("defaults to standard", () => {
    expect(getStoredEffort()).toBe("standard");
  });

  it("round-trips a stored choice", () => {
    storeEffort("thorough");
    expect(getStoredEffort()).toBe("thorough");
  });

  it("ignores unknown stored values", () => {
    window.localStorage.setItem("couplefins:chatEffort", "turbo");
    expect(getStoredEffort()).toBe("standard");
  });

  it("maps choices to API effort levels", () => {
    expect(EFFORT_API_VALUES).toEqual({
      quick: "low",
      standard: "high",
      thorough: "xhigh",
    });
  });
});
