import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface IdentityState {
  currentPersonId: string | null;
  setCurrentPersonId: (id: string) => void;
  clearIdentity: () => void;
}

export const useIdentityStore = create<IdentityState>()(
  persist(
    (set) => ({
      currentPersonId: null,
      setCurrentPersonId: (id) => set({ currentPersonId: id }),
      clearIdentity: () => set({ currentPersonId: null }),
    }),
    {
      name: "couplefins:currentPersonId",
      partialize: (state) => ({ currentPersonId: state.currentPersonId }),
    },
  ),
);

export function useIdentityHydrated() {
  const [hydrated, setHydrated] = useState(
    useIdentityStore.persist.hasHydrated(),
  );

  useEffect(() => {
    const unsub = useIdentityStore.persist.onFinishHydration(() =>
      setHydrated(true),
    );
    return unsub;
  }, []);

  return hydrated;
}
