import { create } from "zustand";

interface IdentityState {
  currentPersonId: string | null;
  currentPersonName: string | null;
  setFromAuthResponse: (person: { id: string; name: string }) => void;
  setCurrentPersonId: (id: string) => void;
  clearIdentity: () => void;
}

export const useIdentityStore = create<IdentityState>()((set) => ({
  currentPersonId: null,
  currentPersonName: null,
  setFromAuthResponse: (person) =>
    set({ currentPersonId: person.id, currentPersonName: person.name }),
  setCurrentPersonId: (id) => set({ currentPersonId: id }),
  clearIdentity: () => set({ currentPersonId: null, currentPersonName: null }),
}));

// One-time cleanup of legacy localStorage key
try {
  localStorage.removeItem("couplefins:currentPersonId");
} catch {
  // SSR or restricted storage — ignore
}
