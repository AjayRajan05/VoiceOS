/** Minimal Alpine store helper for VoiceOS plugin hub stubs. */

const stores = {};

export function createStore(name, model) {
  const store = { ...model };
  stores[name] = store;
  if (typeof window !== "undefined") {
    window.__voiceosStores = window.__voiceosStores || {};
    window.__voiceosStores[name] = store;
  }
  return store;
}

export function getStore(name) {
  return stores[name];
}
