#ifndef PL_VALUE_H
#define PL_VALUE_H

/*
 * PLAN value representation.
 *
 * A pl_val is a 64-bit word:
 *   - bit 63 clear: a direct nat; the low 63 bits are the value.
 *   - bit 63 set:   a tagged pointer; bits 62..56 carry a 7-bit tag and
 *                   bits 55..0 the (8-aligned) address.
 *
 * The tag is a kind cache, valid only for kinds that never mutate in
 * place.  THUNK -> BLACKHOLE -> IND transitions happen under aliasing, so
 * all three share PL_TAG_DEFER and dispatch reads the object header for
 * the true kind.  Consequently WHNF is a register test:
 *   pl_tag(v) < PL_TAG_DEFER.
 *
 */

#include <stdint.h>

#include "axsys/assume.h"

typedef uint64_t pl_val;
typedef uint64_t pl_cell;

#define PL_PTR_BIT   (UINT64_C(1) << 63)
#define PL_ADDR_MASK UINT64_C(0x00ffffffffffffff)
#define PL_NAT63_MAX UINT64_C(0x7fffffffffffffff)

/* Tags live in the top byte (bit 63 implied set). */
#define PL_TAG_NAT   UINT64_C(0x80) /* boxed nat (>= 2^63) */
#define PL_TAG_APP   UINT64_C(0x82)
#define PL_TAG_LAW   UINT64_C(0x83)
#define PL_TAG_PIN   UINT64_C(0x84)
#define PL_TAG_ENV   UINT64_C(0x85)
#define PL_TAG_DEFER UINT64_C(0x86) /* THUNK | BLACKHOLE | IND */

/* Object kinds (authoritative, stored in the header). */
typedef enum {
  PL_K_NAT = 1,
  PL_K_APP,
  PL_K_LAW,
  PL_K_PIN,
  PL_K_THUNK,
  PL_K_ENV,
  PL_K_IND,
  PL_K_BH,   /* TODO move (BH, IND) to newstyle thunks */
  PL_K_FWD,  /* forwarding pointer, exists only during collection */
  PL_K_THKE, /* newstyle thunks, variably sized */
} pl_kind;

/* executioner types for newstyle thunks */
typedef enum {
  PL_BAN_FAST = 1,       /* known exact arity match */
  PL_BAN_SLOW = 2,       /* fallback - possibly over or under applied */
  PL_BAN_PRIM = 3,       /* primop [oppin, arg]: dispatch via the op table */
  PL_BAN_PRIM_KNOWN = 4, /* ingest-resolved primop [opidx, args…] */
  PL_BAN_MASK = 7,       /* low bits: the bane proper */
  PL_BAN_NOUPD = 8,      /* flag: entry-count Zero/Once (occurrence
                            analysis) — no blackhole, no update; re-entry
                            re-evaluates.  Also loses <<loop>> detection,
                            which the Once guarantee makes unreachable. */
} pl_bane;

/*
 * Header word, one per object:
 *   [ kind:8 | flags:4 | meta:20 | cells:32 ]
 * cells is the total size in 8-byte cells including the header.
 */
#define PL_HDR_META_MAX UINT32_C(0xFFFFF)

#define PL_F_NORMAL 0x1u /* deep normal form reached (§ nf) */
#define PL_F_HOLE   0x2u /* currently evaluating */
#define PL_F_PIN_HASHED                                                        \
  0x4u /* PIN hash is finalized and indexed (possibly staged until Save) */
#define PL_F_PIN_PROXY                                                         \
  0x8u /* PIN cell 6 is an atomic canonical-target pl_val, not code */

static inline pl_cell pl_hdr_make(pl_kind kind, uint32_t flags, uint32_t meta,
                                  uint32_t cells) {
  ax_assume(kind != PL_K_APP || cells >= 3,
            "APP requires a head and at least one argument");
  return (pl_cell)(kind & 0xFFu) | ((pl_cell)(flags & 0xFu) << 8) |
         ((pl_cell)(meta & PL_HDR_META_MAX) << 12) | ((pl_cell)cells << 32);
}

static inline pl_kind pl_hdr_kind(pl_cell hdr) {
  return (pl_kind)(hdr & 0xFFu);
}
static inline uint32_t pl_hdr_flags(pl_cell hdr) {
  return (uint32_t)(hdr >> 8) & 0xFu;
}

static inline pl_cell pl_hdr_set_flag(pl_cell hdr, uint32_t flags) {
  uint32_t old = pl_hdr_flags(hdr);
  old |= flags;
  return hdr | ((pl_cell)((old) & 0xFu) << 8);
}

static inline pl_cell pl_hdr_set_meta(pl_cell hdr, uint32_t meta) {
  return (hdr & ~((pl_cell)PL_HDR_META_MAX << 12)) |
         ((pl_cell)(meta & PL_HDR_META_MAX) << 12);
}

static inline uint32_t pl_hdr_meta(pl_cell hdr) {
  return (uint32_t)(hdr >> 12) & PL_HDR_META_MAX;
}
static inline uint32_t pl_hdr_cells(pl_cell hdr) {
  return (uint32_t)(hdr >> 32);
}

/* ── pl_val accessors ──────────────────────────────────────────────────── */

static inline bool pl_is_nat63(pl_val v) {
  return (v & PL_PTR_BIT) == 0;
}
static inline uint64_t pl_nat63(pl_val v) {
  return v;
}
static inline uint64_t pl_tag(pl_val v) {
  return v >> 56;
}

/* Canonical numeric address for range checks and foreign interfaces.  TBI only
 * affects address translation; it does not make a tagged pointer compare equal
 * to the allocation address that it names. */
static inline uintptr_t pl_addr(pl_val v) {
  return (uintptr_t)(v & PL_ADDR_MASK);
}

/* Dereference view.  Apple arm64 ignores the top byte in data addresses, so the
 * value tag can remain in place on the evaluator's hot load/store paths. */
static inline pl_cell* pl_ptr(pl_val v) {
#if AX_USE_TBI
  return (pl_cell*)(uintptr_t)(v);
#else
  return (pl_cell*)pl_addr(v);
#endif
}
static inline pl_val pl_make(uint64_t tag, void* p) {
  return (tag << 56) | ((uint64_t)(uintptr_t)p & PL_ADDR_MASK);
}

/* WHNF needs no memory access except for PL_TAG_DEFER. */
static inline bool pl_is_whnf(pl_val v) {
  return pl_tag(v) != PL_TAG_DEFER;
}

/* True kind: tag, or header load for PL_TAG_DEFER. */
static inline pl_kind pl_kind_of(pl_val v) {
  ax_assume(!pl_is_nat63(v), "pl_kind_of on a direct nat");
  switch (pl_tag(v)) {
  case PL_TAG_NAT:
    return PL_K_NAT;
  case PL_TAG_APP:
    return PL_K_APP;
  case PL_TAG_LAW:
    return PL_K_LAW;
  case PL_TAG_PIN:
    return PL_K_PIN;
  case PL_TAG_ENV:
    return PL_K_ENV;
  default:
    return pl_hdr_kind(*pl_ptr(v));
  }
}

static inline uint64_t pl_tag_for_kind(pl_kind k) {
  switch (k) {
  case PL_K_NAT:
    return PL_TAG_NAT;
  case PL_K_APP:
    return PL_TAG_APP;
  case PL_K_LAW:
    return PL_TAG_LAW;
  case PL_K_PIN:
    return PL_TAG_PIN;
  case PL_K_ENV:
    return PL_TAG_ENV;
  default:
    return PL_TAG_DEFER;
  }
}

/* ── Layouts (cells include the header word) ───────────────────────────── */

#define PL_NAT_CELLS(limbs) (1u + (uint32_t)(limbs))
#define PL_APP_CELLS(n)     (2u + (uint32_t)(n))
#define PL_LAW_CELLS        4u
#define PL_PIN_CELLS(np)    (7u + (uint32_t)(np))
#define PL_THUNK_CELLS      3u
#define PL_ENV_CELLS(n)     (1u + (uint32_t)(n))
#define PL_IND_CELLS        2u
#define PL_THKE_CELLS(n)    (2u + (uint32_t)(n))

/* K_NAT { hdr(meta=used limbs); limb[..] } — mpn limbs, little-endian. */
static inline uint32_t pl_nat_limbs(pl_cell* p) {
  return pl_hdr_meta(p[0]);
}
static inline uint64_t* pl_nat_limb_ptr(pl_cell* p) {
  return (uint64_t*)(p + 1);
}

/* K_APP { hdr(meta=need, n=cells-2); head; arg[n] } — immutable, n >= 1.
 * n excludes the head: every APP has at least two value fields. */
static inline uint32_t pl_app_n(pl_cell* p) {
  return pl_hdr_cells(p[0]) - 2u;
}
static inline uint32_t pl_app_need(pl_cell* p) {
  return pl_hdr_meta(p[0]);
}
static inline pl_val pl_app_head(pl_cell* p) {
  return (pl_val)p[1];
}
static inline pl_val* pl_app_args(pl_cell* p) {
  return (pl_val*)(p + 2);
}

/* K_LAW { hdr; u64 arity; name; body } */
static inline uint64_t pl_law_arity(pl_cell* p) {
  return p[1];
}
static inline pl_val pl_law_name(pl_cell* p) {
  return (pl_val)p[2];
}
static inline pl_val pl_law_body(pl_cell* p) {
  return (pl_val)p[3];
}

/* K_PIN has two representations with the same leading seven cells:
 *
 *   proxy:     { hdr(PROXY, meta=0, cells=7); zero hash; body; target }
 *   canonical: { hdr(HASHED, meta=npins); hash; body; code; pin[npins] }
 *
 * A proxy target is atomically published as a tagged pl_val referring to a
 * canonical PIN.  It is initially zero.  Canonical targets never form chains,
 * and only canonical PINs use cell 6 as the compiled-code cache.  Accessors
 * below transparently delegate through a published target. */
static inline bool pl_pin_is_proxy(pl_cell* p) {
  return (pl_hdr_flags(p[0]) & PL_F_PIN_PROXY) != 0;
}

/* Acquire pairs with pl_pin_set_target's release publication.  Returning zero
 * for a canonical PIN makes this helper safe for generic PIN paths too. */
static inline pl_val pl_pin_proxy_target(pl_cell* p) {
  if (!pl_pin_is_proxy(p))
    return 0;
  return (pl_val)__atomic_load_n(&p[6], __ATOMIC_ACQUIRE);
}

static inline pl_cell* pl_pin_resolved(pl_cell* p) {
  pl_val target = pl_pin_proxy_target(p);
  if (target == 0)
    return p;
  ax_assume(pl_tag(target) == PL_TAG_PIN, "PIN proxy target is not a PIN");
  pl_cell* canonical = pl_ptr(target);
  ax_assume(pl_hdr_kind(canonical[0]) == PL_K_PIN &&
                !pl_pin_is_proxy(canonical) &&
                (pl_hdr_flags(canonical[0]) & PL_F_PIN_HASHED) != 0,
            "PIN proxy target is not canonical");
  return canonical;
}

static inline void pl_pin_set_target(pl_cell* p, pl_val canonical) {
  ax_assume(pl_hdr_kind(p[0]) == PL_K_PIN && pl_pin_is_proxy(p) &&
                pl_hdr_meta(p[0]) == 0 && pl_hdr_cells(p[0]) == PL_PIN_CELLS(0),
            "pl_pin_set_target on a non-proxy PIN");
  ax_assume(pl_tag(canonical) == PL_TAG_PIN, "PIN proxy target is not a PIN");
  pl_cell* target = pl_ptr(canonical);
  ax_assume(pl_hdr_kind(target[0]) == PL_K_PIN && !pl_pin_is_proxy(target) &&
                (pl_hdr_flags(target[0]) & PL_F_PIN_HASHED) != 0,
            "PIN proxy target is not canonical");
  pl_val old = (pl_val)__atomic_load_n(&p[6], __ATOMIC_ACQUIRE);
  ax_assume(old == 0 || old == canonical,
            "PIN proxy target cannot be replaced");
  __atomic_store_n(&p[6], (pl_cell)canonical, __ATOMIC_RELEASE);
}

static inline uint8_t* pl_pin_hash_bytes(pl_cell* p) {
  p = pl_pin_resolved(p);
  return (uint8_t*)(p + 1);
}
static inline pl_val pl_pin_body(pl_cell* p) {
  p = pl_pin_resolved(p);
  return (pl_val)p[5];
}
static inline void* pl_pin_code(pl_cell* p) {
  p = pl_pin_resolved(p);
  if (pl_pin_is_proxy(p))
    return NULL;
  return (void*)(uintptr_t)__atomic_load_n(&p[6], __ATOMIC_ACQUIRE);
}
static inline void pl_pin_set_code(pl_cell* p, void* code) {
  p = pl_pin_resolved(p);
  ax_assume(!pl_pin_is_proxy(p), "pl_pin_set_code on an unresolved PIN proxy");
  __atomic_store_n(&p[6], (pl_cell)(uintptr_t)code, __ATOMIC_RELEASE);
}
static inline uint32_t pl_pin_npins(pl_cell* p) {
  p = pl_pin_resolved(p);
  return pl_hdr_meta(p[0]);
}
static inline pl_val* pl_pin_subpins(pl_cell* p) {
  p = pl_pin_resolved(p);
  return (pl_val*)(p + 7);
}

/* K_THUNK { hdr; env; expr } */
static inline pl_val pl_thunk_env(pl_cell* p) {
  return (pl_val)p[1];
}
static inline pl_val pl_thunk_expr(pl_cell* p) {
  return (pl_val)p[2];
}

/* K_THKE { hdr; bane; arg[n]; } */
/* The full bane word: low 3 bits the bane, bit 3 NOUPD, bits >= 8 a
 * strict-entry mask hint (FAST only). */
static inline uint64_t pl_thke_bane(pl_cell* p) {
  return (uint64_t)p[1];
}

static inline uint32_t pl_thke_n(pl_cell* p) {
  return pl_hdr_cells(p[0]) - 2u;
}

static inline pl_val* pl_thke_args(pl_cell* p) {
  return (pl_val*)(p + 2);
}

/* K_ENV { hdr(n=cells-1); slot[n] } — law activation [self, args…, binds…]. */
static inline uint32_t pl_env_n(pl_cell* p) {
  return pl_hdr_cells(p[0]) - 1u;
}
static inline pl_val* pl_env_slots(pl_cell* p) {
  return (pl_val*)(p + 1);
}

/* K_IND { hdr; target }.  While a legacy K_BH is under evaluation, cell 1
 * retains the thunk env and its expression is rooted by F_UPDATE.b. */
static inline pl_val pl_ind_target(pl_cell* p) {
  return (pl_val)p[1];
}

static inline pl_val pl_resolve(pl_val v) {
  while (!pl_is_nat63(v) && pl_tag(v) == PL_TAG_DEFER &&
         pl_hdr_kind(*pl_ptr(v)) == PL_K_IND)
    v = pl_ind_target(pl_ptr(v));
  return v;
}

/* ── Convenience predicates (WHNF inputs) ──────────────────────────────── */

static inline bool pl_is_nat(pl_val v) {
  return pl_tag(v) <= PL_TAG_NAT;
}

static inline pl_cell* pl_as(uint64_t tag, pl_val v) {
  return pl_tag(v) == tag ? pl_ptr(v) : (pl_cell*)0;
}

#endif
