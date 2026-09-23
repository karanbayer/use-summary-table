// In-process stand-in for Cloudflare KV (AUDIT_LOG). Same get/put shape the
// governance helpers expect. Fine for a single Agentrix replica; not shared
// across replicas — Phase 2 can swap this for Redis/Dynamo without changing
// call sites.

export function createMemoryStore() {
  /** @type {Map<string, { value: string, expiresAt: number|null }>} */
  const map = new Map();

  function purgeIfExpired(key, entry) {
    if (entry.expiresAt != null && Date.now() >= entry.expiresAt) {
      map.delete(key);
      return true;
    }
    return false;
  }

  return {
    async get(key) {
      const entry = map.get(key);
      if (!entry) return null;
      if (purgeIfExpired(key, entry)) return null;
      return entry.value;
    },

    async put(key, value, opts = {}) {
      const ttlSec = opts.expirationTtl;
      const expiresAt =
        typeof ttlSec === "number" && ttlSec > 0
          ? Date.now() + ttlSec * 1000
          : null;
      map.set(key, { value: String(value), expiresAt });
    },

    async delete(key) {
      map.delete(key);
    }
  };
}
