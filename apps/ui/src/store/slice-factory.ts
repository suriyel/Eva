/**
 * createSlice — Zustand slice factory with name-uniqueness guard + devtools registration.
 */
import { create, type StateCreator, type StoreApi, type UseBoundStore } from "zustand";

const registry = new Set<string>();

interface HarnessStoreWindow {
  __HARNESS_STORES__?: Record<string, unknown>;
}

function storeHost(): HarnessStoreWindow {
  return (typeof window !== "undefined" ? window : globalThis) as unknown as HarnessStoreWindow;
}

export function __resetStoreRegistryForTests(): void {
  registry.clear();
  const w = storeHost();
  if (w.__HARNESS_STORES__) w.__HARNESS_STORES__ = {};
}

export function createSlice<S>(
  name: string,
  init: StateCreator<S, [], []>,
): UseBoundStore<StoreApi<S>> {
  if (registry.has(name)) {
    throw new Error(`slice '${name}' already registered`);
  }
  registry.add(name);
  const useStore = create<S>(init);
  // Register on the window for devtools ergonomics (non-fatal if window missing).
  try {
    const w = storeHost();
    if (!w.__HARNESS_STORES__) w.__HARNESS_STORES__ = {};
    w.__HARNESS_STORES__[name] = useStore;
  } catch {
    /* ignore */
  }
  return useStore;
}
