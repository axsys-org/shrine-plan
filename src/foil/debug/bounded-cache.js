// Count and age bounds; reads refresh recency, never freshness.
export class BoundedCache extends Map {
  constructor(limit, ttl = Infinity, entries = [], now = Date.now) {
    super(); this.limit = limit; this.ttl = ttl; this.now = now;
    this.expiry = new Map();
    for (const [key, value] of entries) this.set(key, value);
  }
  set(key, value) {
    super.delete(key); super.set(key, value);
    this.expiry.set(key, this.now() + this.ttl);
    while (this.size > this.limit) this.delete(this.keys().next().value);
    return this;
  }
  has(key) {
    if (super.has(key) && this.expiry.get(key) <= this.now()) this.delete(key);
    return super.has(key);
  }
  get(key) {
    if (!this.has(key)) return undefined;
    const value = super.get(key); super.delete(key); super.set(key, value); return value;
  }
  delete(key) { this.expiry.delete(key); return super.delete(key); }
  clear() { this.expiry.clear(); super.clear(); }
}
