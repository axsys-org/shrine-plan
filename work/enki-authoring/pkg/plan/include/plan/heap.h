#ifndef PL_HEAP_H
#define PL_HEAP_H

/*
 * Semispace Cheney heap with safepoint + reserve discipline.
 *
 * Core invariants (violations abort in debug builds):
 *   I1  the collector runs only at reserve or an explicit safe host boundary
 *   I2  pl_bump never collects; it asserts previously reserved headroom
 *   I3  measure, then build: reserve before each no-collect window
 *   I4  no pl_val in a C local survives a reserve — re-fetch from a root
 *   I6  the collector scans exactly the registered root sources
 *   I9  within one no-collect window, bare pointers are stable
 */

#include <setjmp.h>
#include <pthread.h>
#include <stddef.h>
#include <assert.h>

#include "axsys/profile.h"
#include "plan/value.h"
#include "plan/bytecode.h"

typedef struct pl_store pl_store;
typedef struct pl_heap pl_heap;
typedef struct pl_thread pl_thread;

/* ── Root sources ──────────────────────────────────────────────────────── */

typedef void (*pl_root_visit)(pl_val* slot, void* gc_ctx);
typedef void (*pl_root_source)(pl_root_visit visit, void* gc_ctx,
                               void* src_ctx);

void pl_gc_add_root_source(pl_heap* h, pl_root_source src, void* src_ctx);
void pl_gc_del_root_source(pl_heap* h, pl_root_source src, void* src_ctx);

/* ── Machine frames (eval) — pl_val fields are roots ───────────────────── */

typedef enum {
  PL_F_UPDATE = 1, /* a: thunk/blackhole, b: saved expr for unwind      */
  PL_F_APPLY,      /* b: pending (lazy) argument                        */
  PL_F_SEQ,        /* b: value to evaluate after discarding the result  */
  PL_F_KAL,        /* a: env; resume body-expr decomposition            */
  PL_F_KAPP,       /* a: env, b: (0 f x) expr; force subexprs, then     */
                   /* interpret them (the reference unapp forces)       */
  PL_F_OPENT,      /* op entry: forcing the op's single argument        */
  PL_F_OPARG,      /* primop strict-arg driver                          */
  PL_F_OPDEEP,     /* primop deep (nf) phase over the deep_mask args    */
  PL_F_NF,         /* normalize the incoming value                      */
  PL_F_NFOBJ,      /* a: object being normalized, k: field index        */
  PL_F_EXEC,       /* a: env, ip: pointer  */
  PL_F_EXECV,      /* stack-resident law entry: the [head, args…] group
                      stays on the vstack at b (a nat index); argc =
                      group size; a = 0 until an op that captures an
                      env reifies one on demand.  RET resets to b.     */
  PL_F_UPD,        /* newstyle thunk update chain: a is the first target;
                      argbase owns argc-1 further targets in ustack;
                      argc may be zero after weak-target collection */
  PL_F_TRY,        /* exception barrier (op 66 Try); argbase: vsp mark  */
  PL_F_JUDGE,      /* forcing a law-body chain node; argbase: hbase     */
  PL_F_NIL,        /* RETURN planNil(v): 1 if the value is 0, else 0    */
  PL_F_PROF,       /* Tracy law-attribution boundary; a: law head       */
  PL_F_APPLYN,     /* n-ary apply: argc pending args parked on the      */
                   /* vstack at argbase; the head slot is argbase-1     */
  PL_F_MEMO,       /* memo barrier (op 66 Memo); a: f pin, b: x pin,    */
                   /* epoch: effect-epoch watermark at entry            */
  PL_F_PURE,      /* bounded, effect-free, deeply normalized application */
  PL_F_KIND_COUNT, /* sentinel: sizes pl_run's RETURN dispatch table    */
} pl_frame_kind;

typedef struct pl_frame {
  uint8_t kind;
  uint32_t k;       /* field index / mask cursor / ip */
  uint32_t argbase; /* offset into vstack (never a pointer) */
  uint32_t argc;
  pl_val a;                /* root */
  pl_val b;                /* root */
  union {                  /* kind-exclusive state: */
    uint64_t opset;        /*   op set number (F_OPENT) */
    pl_code* code;         /*   bytecode (F_EXEC) */
    uint32_t op;           /*   op descriptor index (F_OPARG/F_OPDEEP) */
    uint64_t profile_mark; /* profile generation watermark (F_TRY) */
    uint64_t epoch;        /* effect-epoch watermark (F_MEMO) */
  };
#ifdef TRACY_ENABLE
  ax_profile_zone_ctx profile_ctx;
  bool profile_live;
#endif
} pl_frame;

#ifndef TRACY_ENABLE
static_assert(sizeof(pl_frame) == 40, "pl_frame grew");
#endif

#ifdef PL_CACHE_STATS
#define PL_CACHE_KIND_CAP      16u
#define PL_CACHE_FRAME_CAP     32u
#define PL_CACHE_DEPTH_BUCKETS 16u

typedef enum {
  PL_CACHE_MOVE_TAIL_FAST,
  PL_CACHE_MOVE_TAIL_KNOWN,
  PL_CACHE_MOVE_TAIL_SLOW,
  PL_CACHE_MOVE_CALL_KNOWN,
  PL_CACHE_MOVE_APPLY_SPLICE,
  PL_CACHE_MOVE_COUNT,
} pl_cache_move_kind;

typedef struct pl_cache_stats {
  uint64_t alloc_objects[PL_CACHE_KIND_CAP];
  uint64_t alloc_cells[PL_CACHE_KIND_CAP];

  uint64_t gc_collections;
  uint64_t gc_copied_objects;
  uint64_t gc_copied_cells;
  uint64_t gc_root_slots;
  uint64_t gc_pointer_slots;
  uint64_t gc_store_terminals;
  uint64_t gc_indirections;

  uint64_t vpushes;
  uint64_t max_vsp;
  uint64_t frame_pushes;
  uint64_t max_fsp;
  uint64_t max_stack_bytes;
  uint64_t frame_depth[PL_CACHE_DEPTH_BUCKETS];
  uint64_t gc_frame_kinds[PL_CACHE_FRAME_CAP];
  uint64_t upd_frames;
  uint64_t upd_chains;
  uint64_t upd_max_run;
  uint64_t upd_run_depth[PL_CACHE_DEPTH_BUCKETS];
  uint64_t upd_side_pushes;
  uint64_t upd_max_usp;

  uint64_t vstack_move_calls;
  uint64_t vstack_move_bytes;
  uint64_t vstack_move_site_calls[PL_CACHE_MOVE_COUNT];
  uint64_t vstack_move_site_bytes[PL_CACHE_MOVE_COUNT];
  uint64_t vstack_move_same_calls[PL_CACHE_MOVE_COUNT];
  uint64_t vstack_move_same_bytes[PL_CACHE_MOVE_COUNT];
  uint64_t vstack_move_one_calls[PL_CACHE_MOVE_COUNT];
  uint64_t vstack_move_one_bytes[PL_CACHE_MOVE_COUNT];

  uint64_t env_lookups;
  uint64_t env_hits;
  uint64_t env_probes;
  uint64_t env_max_probes;
  uint64_t env_cloned_entries;
  uint64_t env_root_slots;
} pl_cache_stats;
#endif

/* ── Thread ────────────────────────────────────────────────────────────── */

typedef struct pl_profile_zone {
  pl_val handle; /* rooted opaque identity returned by ZoneStart */
  uint8_t* name;
  size_t name_n;
  uint64_t generation;
#ifdef TRACY_ENABLE
  ax_profile_zone_ctx tracy_ctx;
#endif
  bool live; /* at least one physical backend currently has this segment */
} pl_profile_zone;

struct pl_thread {
  pl_heap* heap;

  pl_val* vstack; /* operand/value stack — root source */
  size_t vsp, vcap;

  pl_frame* fstack; /* machine frames — root source */
  size_t fsp, fcap;

  /* Dense roots owned by coalesced PL_F_UPD frames.  A singleton remains
   * entirely in its ordinary frame; only a consecutive chain spills here. */
  pl_val* ustack;
  size_t usp, ucap;

  pl_val exn;          /* pending PLAN_EXN value — root slot */
  const char* exn_msg; /* non-NULL: runtime error, not catchable by Try */
  jmp_buf* handler;

  /*
   * Suspension state (driven by pl_thread_run in eval.c).
   * A suspended thread is a complete continuation: value stack, frame
   * stack, and these slots.  All pl_val fields here are root slots.
   */
  uint64_t fuel;         /* reductions remaining this quantum */
  uint32_t centry_depth; /* >0: native frames below us — suspension deferred */
  bool suspendable;      /* true only while pl_thread_run drives this thread */
  bool pending_yield;    /* fuel hit 0 inside a C-entry region */
  uint8_t resume_kind;   /* pl_resume_kind */
  uint8_t status;        /* last pl_run_status */
  size_t base_vsp;       /* entry watermarks: EXN unwinds to these; */
  size_t base_fsp;       /* the run is DONE when fsp returns to base_fsp */
  pl_val resume_val;     /* root: value to EVAL or RETURN on re-entry */
  pl_val blocked_on;     /* root: effect request while blocked */
  pl_val result;         /* root: final value after PL_RUN_DONE */

  /* Bumped at every effect initiation (op 82/83, Trace, Save): an
   * F_MEMO barrier records its result only if this is unchanged, so
   * caching can skip work but never effects. */
  uint64_t effect_epoch;

  /* Explicit op-83 profiling zones.  Logical zones survive suspension and
   * normal entry returns; physical Tracy/JSON segments do not. */
  pl_profile_zone* profile_zones;
  size_t profile_zone_n, profile_zone_cap;
  uint64_t profile_next_generation;
  uint64_t profile_run_mark;
  uint64_t profile_lane;
  bool profile_json_named;

  /* The reference vMode: op 82 (rplan I/O) is callable only in RPLAN
   * mode (REPL / snapshot execution), never while assembling modules. */
  bool rplan_f;
  uint32_t pure_depth;
  uint64_t pure_remaining;

  /* When non-NULL, ReadFile and ReadFolder resolve their arguments relative
   * to this root and refuse paths whose canonical target escapes it. */
  const char* rplan_file_root_c;

  /* Called immediately before a descriptor-marked host effect begins.
   * Embedders use this to move an effectful green thread onto a syscall-safe
   * executor; the plan layer otherwise treats it as opaque. */
  void (*rplan_effect_f)(struct pl_thread* t);

  /* Opaque embedder slot (the actor runtime stores its er_actor here so
   * the pl_io_hook can attribute effects); never touched by the plan
   * layer. */
  void* host;

#ifdef PL_CACHE_STATS
  pl_cache_stats cache_stats;
#endif
};

#ifdef PL_CACHE_STATS
static inline void pl_cache_stat_alloc(pl_thread* t, pl_kind kind,
                                       size_t cells) {
  if ((unsigned)kind < PL_CACHE_KIND_CAP) {
    t->cache_stats.alloc_objects[kind]++;
    t->cache_stats.alloc_cells[kind] += cells;
  }
}

static inline unsigned pl_cache_depth_bucket(size_t depth) {
  unsigned bucket = 0;
  while (depth > 1 && bucket + 1 < PL_CACHE_DEPTH_BUCKETS) {
    depth = (depth + 1) / 2;
    bucket++;
  }
  return bucket;
}

static inline void pl_cache_stat_vpush(pl_thread* t) {
  t->cache_stats.vpushes++;
  if (t->vsp > t->cache_stats.max_vsp)
    t->cache_stats.max_vsp = t->vsp;
}

static inline void pl_cache_stat_fpush(pl_thread* t) {
  t->cache_stats.frame_pushes++;
  if (t->fsp > t->cache_stats.max_fsp)
    t->cache_stats.max_fsp = t->fsp;
  size_t bytes = t->fsp * sizeof(pl_frame) + t->usp * sizeof(pl_val);
  if (bytes > t->cache_stats.max_stack_bytes)
    t->cache_stats.max_stack_bytes = bytes;
  t->cache_stats.frame_depth[pl_cache_depth_bucket(t->fsp)]++;
}

static inline void pl_cache_stat_upd_push(pl_thread* t, uint32_t run) {
  t->cache_stats.upd_frames++;
  if (run == 1)
    t->cache_stats.upd_chains++;
  if (run > t->cache_stats.upd_max_run)
    t->cache_stats.upd_max_run = run;
  t->cache_stats.upd_run_depth[pl_cache_depth_bucket(run)]++;
}

static inline void pl_cache_stat_upush(pl_thread* t) {
  t->cache_stats.upd_side_pushes++;
  if (t->usp > t->cache_stats.upd_max_usp)
    t->cache_stats.upd_max_usp = t->usp;
  size_t bytes = t->fsp * sizeof(pl_frame) + t->usp * sizeof(pl_val);
  if (bytes > t->cache_stats.max_stack_bytes)
    t->cache_stats.max_stack_bytes = bytes;
}

static inline void pl_cache_stat_vstack_move(pl_thread* t,
                                             pl_cache_move_kind kind,
                                             size_t bytes,
                                             ptrdiff_t distance_cells) {
  t->cache_stats.vstack_move_calls++;
  t->cache_stats.vstack_move_bytes += bytes;
  t->cache_stats.vstack_move_site_calls[kind]++;
  t->cache_stats.vstack_move_site_bytes[kind] += bytes;
  if (distance_cells == 0) {
    t->cache_stats.vstack_move_same_calls[kind]++;
    t->cache_stats.vstack_move_same_bytes[kind] += bytes;
  } else if (distance_cells == 1 || distance_cells == -1) {
    t->cache_stats.vstack_move_one_calls[kind]++;
    t->cache_stats.vstack_move_one_bytes[kind] += bytes;
  }
}

static inline void pl_cache_stat_env_lookup(pl_thread* t, size_t probes,
                                            bool hit) {
  t->cache_stats.env_lookups++;
  t->cache_stats.env_probes += probes;
  if (hit)
    t->cache_stats.env_hits++;
  if (probes > t->cache_stats.env_max_probes)
    t->cache_stats.env_max_probes = probes;
}

static inline void pl_cache_stat_env_clone(pl_thread* t) {
  t->cache_stats.env_cloned_entries++;
}

static inline void pl_cache_stat_env_roots(pl_thread* t, size_t slots) {
  t->cache_stats.env_root_slots += slots;
}
#else
#define pl_cache_stat_alloc(t, kind, cells)                       ((void)0)
#define pl_cache_stat_vpush(t)                                    ((void)0)
#define pl_cache_stat_fpush(t)                                    ((void)0)
#define pl_cache_stat_upd_push(t, run)                            ((void)0)
#define pl_cache_stat_upush(t)                                    ((void)0)
#define pl_cache_stat_vstack_move(t, kind, bytes, distance_cells) ((void)0)
#define pl_cache_stat_env_lookup(t, probes, hit)                  ((void)0)
#define pl_cache_stat_env_clone(t)                                ((void)0)
#define pl_cache_stat_env_roots(t, slots)                         ((void)0)
#endif

pl_heap* pl_heap_new(size_t cells, pl_store* store);
void pl_heap_free(pl_heap* h);
pl_store* pl_heap_store(pl_heap* h);

pl_thread* pl_thread_new(pl_heap* h);
void pl_thread_free(pl_thread* t);

/* ── The three allocation entry points ─────────────────────────────────── */

/* The ONLY collecting path; postcondition: headroom >= cells. */
void pl_gc_reserve(pl_thread* t, size_t cells);

/* Bump allocation; never collects; hard-asserts headroom (I2). */
pl_cell* pl_bump(pl_thread* t, size_t cells);

/* Remaining headroom in cells (for tests/diagnostics). */
size_t pl_gc_headroom(pl_thread* t);
/* Cells of live data after the last collection (diagnostics). */
size_t pl_gc_live_cells(pl_heap* h);
/*
 * Collect at a safe host boundary only after enough allocation has happened
 * to amortize copying the current live set.  The allocation floor prevents
 * tiny heaps/live sets from collecting on every boundary.  Returns true when
 * a collection ran; reserve remains the correctness-critical collector.
 */
bool pl_gc_collect_if_pressure(pl_thread* t, size_t allocation_floor_cells);
void pl_gc_collect_now(pl_thread* t); /* for tests */
/* Collect and release oversized semispaces at a dormant machine boundary. */
void pl_gc_trim(pl_thread* t);

/* ── No-collect windows (debug accounting) ─────────────────────────────── */

#ifndef NDEBUG
void pl_gc_forbid(pl_heap* h);
void pl_gc_allow(pl_heap* h);
#define PL_GC_FORBID(t) pl_gc_forbid((t)->heap)
#define PL_GC_ALLOW(t)  pl_gc_allow((t)->heap)
#else
#define PL_GC_FORBID(t) ((void)0)
#define PL_GC_ALLOW(t)  ((void)0)
#endif

/* ── Value/frame stack helpers (plain malloc arrays, growable) ─────────── */

void pl_vstack_grow(pl_thread* t);
void pl_fstack_grow(pl_thread* t);
void pl_ustack_grow(pl_thread* t);

static inline void pl_vpush(pl_thread* t, pl_val v) {
  if (t->vsp == t->vcap)
    pl_vstack_grow(t);
  t->vstack[t->vsp++] = v;
  pl_cache_stat_vpush(t);
}

static inline pl_val pl_vpop(pl_thread* t) {
  return t->vstack[--t->vsp];
}

static inline pl_val pl_vreplace(pl_thread* t, uint32_t n, pl_val r) {
  assert(n >= 1 && t->vsp >= n);
  t->vsp -= n - 1;
  t->vstack[t->vsp - 1] = r;
  return r;
}

/* read, n down from TOS */
static inline pl_val* pl_vpeek(pl_thread* t, uint32_t n) {
  assert(n <= t->vsp);
  return &t->vstack[t->vsp - n];
}

static inline pl_frame* pl_fpush(pl_thread* t) {
  if (t->fsp == t->fcap)
    pl_fstack_grow(t);
  pl_frame* f = &t->fstack[t->fsp++];
  pl_cache_stat_fpush(t);
  f->a = 0;
  f->b = 0;
#ifdef TRACY_ENABLE
  f->profile_ctx = (ax_profile_zone_ctx){0};
  f->profile_live = false;
#endif
  return f;
}

static inline void pl_upush(pl_thread* t, pl_val v) {
  if (t->usp == t->ucap)
    pl_ustack_grow(t);
  t->ustack[t->usp++] = v;
  pl_cache_stat_upush(t);
}

#endif
