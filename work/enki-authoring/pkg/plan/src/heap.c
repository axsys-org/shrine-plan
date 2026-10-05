#include "plan/heap.h"

#include <inttypes.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

#include "axsys/assume.h"
#include "axsys/perf.h"
#include "internal.h"
#include "plan/store.h"

#ifdef PL_CACHE_STATS
static pthread_mutex_t pl_cache_stats_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_once_t pl_cache_stats_once = PTHREAD_ONCE_INIT;
static pl_cache_stats pl_cache_stats_total;
static uint64_t pl_cache_stats_threads;

static const char* const pl_cache_kind_names[PL_CACHE_KIND_CAP] = {
    [PL_K_NAT] = "NAT",   [PL_K_APP] = "APP",     [PL_K_LAW] = "LAW",
    [PL_K_PIN] = "PIN",   [PL_K_THUNK] = "THUNK", [PL_K_ENV] = "ENV",
    [PL_K_IND] = "IND",   [PL_K_BH] = "BH",       [PL_K_FWD] = "FWD",
    [PL_K_THKE] = "THKE",
};

static const char* const pl_cache_frame_names[PL_CACHE_FRAME_CAP] = {
    [PL_F_UPDATE] = "UPDATE", [PL_F_APPLY] = "APPLY",
    [PL_F_SEQ] = "SEQ",       [PL_F_KAL] = "KAL",
    [PL_F_KAPP] = "KAPP",     [PL_F_OPENT] = "OPENT",
    [PL_F_OPARG] = "OPARG",   [PL_F_OPDEEP] = "OPDEEP",
    [PL_F_NF] = "NF",         [PL_F_NFOBJ] = "NFOBJ",
    [PL_F_EXEC] = "EXEC",     [PL_F_EXECV] = "EXECV",
    [PL_F_UPD] = "UPD",       [PL_F_TRY] = "TRY",
    [PL_F_JUDGE] = "JUDGE",   [PL_F_NIL] = "NIL",
    [PL_F_PROF] = "PROF",     [PL_F_APPLYN] = "APPLYN",
    [PL_F_MEMO] = "MEMO",
};

static const char* const pl_cache_move_names[PL_CACHE_MOVE_COUNT] = {
    [PL_CACHE_MOVE_TAIL_FAST] = "tail_fast",
    [PL_CACHE_MOVE_TAIL_KNOWN] = "tail_known",
    [PL_CACHE_MOVE_TAIL_SLOW] = "tail_slow",
    [PL_CACHE_MOVE_CALL_KNOWN] = "call_known",
    [PL_CACHE_MOVE_APPLY_SPLICE] = "apply_splice",
};

static void pl_cache_stats_print(void) {
  const pl_cache_stats* s = &pl_cache_stats_total;
  uint64_t alloc_objects = 0, alloc_cells = 0;
  for (unsigned i = 0; i < PL_CACHE_KIND_CAP; i++) {
    alloc_objects += s->alloc_objects[i];
    alloc_cells += s->alloc_cells[i];
  }
  fprintf(stderr,
          "PLAN_CACHE_STATS summary threads=%" PRIu64 " alloc_objects=%" PRIu64
          " alloc_cells=%" PRIu64 "\n",
          pl_cache_stats_threads, alloc_objects, alloc_cells);
  for (unsigned i = 0; i < PL_CACHE_KIND_CAP; i++) {
    if (s->alloc_objects[i] == 0)
      continue;
    fprintf(stderr,
            "PLAN_CACHE_STATS alloc kind=%s objects=%" PRIu64 " cells=%" PRIu64
            "\n",
            pl_cache_kind_names[i] == NULL ? "UNKNOWN" : pl_cache_kind_names[i],
            s->alloc_objects[i], s->alloc_cells[i]);
  }
  fprintf(stderr,
          "PLAN_CACHE_STATS gc collections=%" PRIu64 " copied_objects=%" PRIu64
          " copied_cells=%" PRIu64 " root_slots=%" PRIu64
          " pointer_slots=%" PRIu64 " store_terminals=%" PRIu64
          " indirections=%" PRIu64 "\n",
          s->gc_collections, s->gc_copied_objects, s->gc_copied_cells,
          s->gc_root_slots, s->gc_pointer_slots, s->gc_store_terminals,
          s->gc_indirections);
  fprintf(stderr,
          "PLAN_CACHE_STATS stacks vpushes=%" PRIu64 " max_vsp=%" PRIu64
          " frame_pushes=%" PRIu64 " max_fsp=%" PRIu64
          " max_stack_bytes=%" PRIu64 " move_calls=%" PRIu64
          " move_bytes=%" PRIu64 "\n",
          s->vpushes, s->max_vsp, s->frame_pushes, s->max_fsp,
          s->max_stack_bytes, s->vstack_move_calls, s->vstack_move_bytes);
  fprintf(stderr, "PLAN_CACHE_STATS frame_depth");
  for (unsigned i = 0; i < PL_CACHE_DEPTH_BUCKETS; i++)
    fprintf(stderr, " b%u=%" PRIu64, i, s->frame_depth[i]);
  fputc('\n', stderr);
  fprintf(stderr,
          "PLAN_CACHE_STATS upd_chain frames=%" PRIu64 " chains=%" PRIu64
          " max_run=%" PRIu64 " side_pushes=%" PRIu64 " max_usp=%" PRIu64 "\n",
          s->upd_frames, s->upd_chains, s->upd_max_run, s->upd_side_pushes,
          s->upd_max_usp);
  fprintf(stderr, "PLAN_CACHE_STATS upd_run_depth");
  for (unsigned i = 0; i < PL_CACHE_DEPTH_BUCKETS; i++)
    fprintf(stderr, " b%u=%" PRIu64, i, s->upd_run_depth[i]);
  fputc('\n', stderr);
  for (unsigned i = 0; i < PL_CACHE_FRAME_CAP; i++) {
    if (s->gc_frame_kinds[i] == 0)
      continue;
    fprintf(stderr, "PLAN_CACHE_STATS gc_frame kind=%s visits=%" PRIu64 "\n",
            pl_cache_frame_names[i] == NULL ? "UNKNOWN"
                                            : pl_cache_frame_names[i],
            s->gc_frame_kinds[i]);
  }
  for (unsigned i = 0; i < PL_CACHE_MOVE_COUNT; i++) {
    fprintf(stderr,
            "PLAN_CACHE_STATS move site=%s calls=%" PRIu64 " bytes=%" PRIu64
            " same_calls=%" PRIu64 " same_bytes=%" PRIu64 " one_calls=%" PRIu64
            " one_bytes=%" PRIu64 "\n",
            pl_cache_move_names[i], s->vstack_move_site_calls[i],
            s->vstack_move_site_bytes[i], s->vstack_move_same_calls[i],
            s->vstack_move_same_bytes[i], s->vstack_move_one_calls[i],
            s->vstack_move_one_bytes[i]);
  }
  fprintf(stderr,
          "PLAN_CACHE_STATS env lookups=%" PRIu64 " hits=%" PRIu64
          " probes=%" PRIu64 " max_probes=%" PRIu64 " cloned_entries=%" PRIu64
          " root_slots=%" PRIu64 "\n",
          s->env_lookups, s->env_hits, s->env_probes, s->env_max_probes,
          s->env_cloned_entries, s->env_root_slots);
}

static void pl_cache_stats_register(void) {
  ax_assume(atexit(pl_cache_stats_print) == 0,
            "could not register cache-stat reporter");
}

static void pl_cache_stats_merge(const pl_cache_stats* s) {
  pthread_mutex_lock(&pl_cache_stats_mu);
  pl_cache_stats_threads++;
  for (unsigned i = 0; i < PL_CACHE_KIND_CAP; i++) {
    pl_cache_stats_total.alloc_objects[i] += s->alloc_objects[i];
    pl_cache_stats_total.alloc_cells[i] += s->alloc_cells[i];
  }
#define PL_CACHE_ADD(field) pl_cache_stats_total.field += s->field
  PL_CACHE_ADD(gc_collections);
  PL_CACHE_ADD(gc_copied_objects);
  PL_CACHE_ADD(gc_copied_cells);
  PL_CACHE_ADD(gc_root_slots);
  PL_CACHE_ADD(gc_pointer_slots);
  PL_CACHE_ADD(gc_store_terminals);
  PL_CACHE_ADD(gc_indirections);
  PL_CACHE_ADD(vpushes);
  PL_CACHE_ADD(frame_pushes);
  PL_CACHE_ADD(upd_frames);
  PL_CACHE_ADD(upd_chains);
  PL_CACHE_ADD(upd_side_pushes);
  PL_CACHE_ADD(vstack_move_calls);
  PL_CACHE_ADD(vstack_move_bytes);
  PL_CACHE_ADD(env_lookups);
  PL_CACHE_ADD(env_hits);
  PL_CACHE_ADD(env_probes);
  PL_CACHE_ADD(env_cloned_entries);
  PL_CACHE_ADD(env_root_slots);
#undef PL_CACHE_ADD
  if (s->max_vsp > pl_cache_stats_total.max_vsp)
    pl_cache_stats_total.max_vsp = s->max_vsp;
  if (s->max_fsp > pl_cache_stats_total.max_fsp)
    pl_cache_stats_total.max_fsp = s->max_fsp;
  if (s->max_stack_bytes > pl_cache_stats_total.max_stack_bytes)
    pl_cache_stats_total.max_stack_bytes = s->max_stack_bytes;
  if (s->upd_max_run > pl_cache_stats_total.upd_max_run)
    pl_cache_stats_total.upd_max_run = s->upd_max_run;
  if (s->upd_max_usp > pl_cache_stats_total.upd_max_usp)
    pl_cache_stats_total.upd_max_usp = s->upd_max_usp;
  if (s->env_max_probes > pl_cache_stats_total.env_max_probes)
    pl_cache_stats_total.env_max_probes = s->env_max_probes;
  for (unsigned i = 0; i < PL_CACHE_DEPTH_BUCKETS; i++) {
    pl_cache_stats_total.frame_depth[i] += s->frame_depth[i];
    pl_cache_stats_total.upd_run_depth[i] += s->upd_run_depth[i];
  }
  for (unsigned i = 0; i < PL_CACHE_FRAME_CAP; i++)
    pl_cache_stats_total.gc_frame_kinds[i] += s->gc_frame_kinds[i];
  for (unsigned i = 0; i < PL_CACHE_MOVE_COUNT; i++) {
    pl_cache_stats_total.vstack_move_site_calls[i] +=
        s->vstack_move_site_calls[i];
    pl_cache_stats_total.vstack_move_site_bytes[i] +=
        s->vstack_move_site_bytes[i];
    pl_cache_stats_total.vstack_move_same_calls[i] +=
        s->vstack_move_same_calls[i];
    pl_cache_stats_total.vstack_move_same_bytes[i] +=
        s->vstack_move_same_bytes[i];
    pl_cache_stats_total.vstack_move_one_calls[i] +=
        s->vstack_move_one_calls[i];
    pl_cache_stats_total.vstack_move_one_bytes[i] +=
        s->vstack_move_one_bytes[i];
  }
  pthread_mutex_unlock(&pl_cache_stats_mu);
}
#endif

typedef struct pl_root_entry {
  pl_root_source fn;
  void* ctx;
} pl_root_entry;

struct pl_heap {
  pl_cell* from; /* active semispace; bump frontier lives here */
  pl_cell* to;
  pl_cell* free;
  pl_cell* limit;
  size_t cells; /* per-space size */
  size_t live_cells;
  pl_store* store;
  pl_root_entry* roots;
  size_t nroots, rootcap;
#ifndef NDEBUG
  int forbid_depth;
#endif
};

/* ── Heap lifecycle ────────────────────────────────────────────────────── */

static pl_cell* pl_space_alloc(size_t cells) {
  pl_cell* p = mmap(NULL, cells * sizeof(pl_cell), PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANON, -1, 0);
  ax_assume(p != MAP_FAILED, "heap semispace allocation failed (%zu cells)", cells);
  ax_assume(((uintptr_t)p & 7u) == 0, "semispace not 8-aligned");
  ax_assume(((uintptr_t)(p + cells) & ~PL_ADDR_MASK) == 0,
            "heap address exceeds 56 bits");
  return p;
}

static void pl_space_free(pl_cell* space, size_t cells) {
  (void)munmap(space, cells * sizeof(pl_cell));
}
static void pl_space_discard(pl_cell* space, size_t cells) {
#if defined(__APPLE__)
  (void)madvise(space, cells * sizeof(pl_cell), MADV_FREE_REUSABLE);
#else
  (void)madvise(space, cells * sizeof(pl_cell), MADV_DONTNEED);
#endif
}
static void pl_space_reuse(pl_cell* space, size_t cells) {
#if defined(__APPLE__)
  (void)madvise(space, cells * sizeof(pl_cell), MADV_FREE_REUSE);
#else
  (void)space; (void)cells;
#endif
}

pl_heap* pl_heap_new(size_t cells, pl_store* store) {
  if (cells < 4096)
    cells = 4096;
  pl_heap* h = calloc(1, sizeof(*h));
  ax_assume(h != NULL, "oom");
  h->cells = cells;
  h->from = pl_space_alloc(cells);
  h->to = pl_space_alloc(cells);
  h->free = h->from;
  h->limit = h->from + cells;
  h->store = store;
  return h;
}

void pl_heap_free(pl_heap* h) {
  if (h == NULL)
    return;
  pl_space_free(h->from, h->cells);
  pl_space_free(h->to, h->cells);
  free(h->roots);
  free(h);
}

pl_store* pl_heap_store(pl_heap* h) {
  return h->store;
}

#ifndef NDEBUG
void pl_gc_forbid(pl_heap* h) {
  h->forbid_depth++;
}
void pl_gc_allow(pl_heap* h) {
  ax_assume(h->forbid_depth > 0, "GC_ALLOW without matching GC_FORBID");
  h->forbid_depth--;
}
#endif

/* ── Root sources ──────────────────────────────────────────────────────── */

void pl_gc_add_root_source(pl_heap* h, pl_root_source src, void* src_ctx) {
  if (h->nroots == h->rootcap) {
    h->rootcap = h->rootcap ? h->rootcap * 2 : 8;
    h->roots = realloc(h->roots, h->rootcap * sizeof(*h->roots));
    ax_assume(h->roots != NULL, "oom");
  }
  h->roots[h->nroots++] = (pl_root_entry){src, src_ctx};
}

void pl_gc_del_root_source(pl_heap* h, pl_root_source src, void* src_ctx) {
  for (size_t i = 0; i < h->nroots; i++) {
    if (h->roots[i].fn == src && h->roots[i].ctx == src_ctx) {
      h->roots[i] = h->roots[h->nroots - 1];
      h->nroots--;
      return;
    }
  }
  ax_abort("pl_gc_del_root_source: source not registered");
}

/* ── Cheney collection ─────────────────────────────────────────────────── */

typedef struct pl_gc_ctx {
  pl_heap* h;
  pl_cell* target;
  pl_cell* target_free;
#ifdef PL_CACHE_STATS
  pl_thread* thread;
#endif
} pl_gc_ctx;

#ifndef NDEBUG
/* Store values are collector terminals.  A store-resident proxy is therefore
 * valid only when its unresolved body (or its published target) is itself a
 * store value.  Checking the direct edge here catches the dangerous
 * store-to-moving-heap case at the first collection that observes it. */
static void pl_gc_check_store_pin(pl_gc_ctx* gc, pl_val v) {
  pl_cell* p = pl_ptr(v);
  if (pl_hdr_kind(p[0]) != PL_K_PIN || !pl_pin_is_proxy(p))
    return;
  ax_assume(pl_hdr_meta(p[0]) == 0 && pl_hdr_cells(p[0]) == PL_PIN_CELLS(0),
            "store PIN proxy has a non-proxy layout");
  pl_val target = pl_pin_proxy_target(p);
  pl_val edge = target != 0 ? target : (pl_val)p[5];
  ax_assume(pl_is_nat63(edge) || pl_store_owns(gc->h->store, edge),
            "store PIN proxy points into a moving heap");
  if (target != 0) {
    ax_assume(pl_tag(target) == PL_TAG_PIN,
              "store PIN proxy target is not a PIN");
    pl_cell* canonical = pl_ptr(target);
    ax_assume(pl_hdr_kind(canonical[0]) == PL_K_PIN &&
                  !pl_pin_is_proxy(canonical) &&
                  (pl_hdr_flags(canonical[0]) & PL_F_PIN_HASHED) != 0,
              "store PIN proxy target is not canonical");
  }
}

static void pl_gc_check_local_pointer(pl_gc_ctx* gc, pl_val v) {
  uintptr_t addr = pl_addr(v);
  uintptr_t lo = (uintptr_t)gc->h->from;
  uintptr_t hi = (uintptr_t)gc->h->free;
  ax_assume((addr & (sizeof(pl_cell) - 1u)) == 0 && addr >= lo && addr < hi,
            "collector observed a pointer owned by another heap");
}
#endif

static pl_val pl_forward(pl_gc_ctx* gc, pl_val v) {
#ifdef PL_CACHE_STATS
  gc->thread->cache_stats.gc_pointer_slots++;
#endif
  for (;;) {
    if (pl_is_nat63(v))
      return v;
    if (gc->h->store != NULL && pl_store_owns(gc->h->store, v)) {
#ifdef PL_CACHE_STATS
      gc->thread->cache_stats.gc_store_terminals++;
#endif
#ifndef NDEBUG
      pl_gc_check_store_pin(gc, v);
#endif
      return v; /* store region is non-moving and closed */
    }
    pl_cell* p = pl_ptr(v);
#ifndef NDEBUG
    pl_gc_check_local_pointer(gc, v);
#endif
    pl_cell hdr = p[0];
    pl_kind kind = pl_hdr_kind(hdr);
    if (kind == PL_K_FWD)
      return (pl_val)p[1];
    if (kind == PL_K_IND) {
#ifdef PL_CACHE_STATS
      gc->thread->cache_stats.gc_indirections++;
#endif
      /* Short-circuit indirections during evacuation; the slot gets the
       * target's stable tag for free. */
      v = (pl_val)p[1];
      continue;
    }
    uint32_t cells = pl_hdr_cells(hdr);
#ifndef NDEBUG
    ax_assume(cells != 0 &&
                  (size_t)cells <=
                      ((uintptr_t)gc->h->free - pl_addr(v)) / sizeof(pl_cell),
              "collector observed an invalid heap object size");
#endif
    pl_cell* np = gc->target_free;
    gc->target_free += cells;
#ifdef PL_CACHE_STATS
    gc->thread->cache_stats.gc_copied_objects++;
    gc->thread->cache_stats.gc_copied_cells += cells;
#endif
    memcpy(np, p, cells * sizeof(pl_cell));
    pl_val nv = pl_make(pl_tag_for_kind(kind), np);
    p[0] = pl_hdr_make(PL_K_FWD, 0, 0, cells);
    p[1] = nv;
    return nv;
  }
}

static void pl_gc_visit(pl_val* slot, void* gc_ctx) {
  pl_gc_ctx* gc = gc_ctx;
#ifdef PL_CACHE_STATS
  gc->thread->cache_stats.gc_root_slots++;
#endif
  *slot = pl_forward(gc, *slot);
}

static void pl_cheney_scan(pl_gc_ctx* gc) {
  pl_cell* scan = gc->target;
  while (scan < gc->target_free) {
    pl_cell hdr = scan[0];
    pl_kind kind = pl_hdr_kind(hdr);
    uint32_t cells = pl_hdr_cells(hdr);
    uint32_t first = 0, count = 0;
    switch (kind) {
    case PL_K_NAT:
      break;
    case PL_K_APP:
    case PL_K_ENV:
      first = 1;
      count = cells - 1;
      break;
    case PL_K_LAW:
      first = 2;
      count = 2;
      break;
    case PL_K_THUNK:
      first = 1;
      count = 2;
      break;
    case PL_K_THKE:
      first = 2;
      count = cells - 2;
      break;
    case PL_K_IND:
    case PL_K_BH:
      first = 1;
      count = 1;
      break;
    case PL_K_PIN: {
      ax_assume(pl_pin_is_proxy(scan) && pl_hdr_meta(hdr) == 0 &&
                    cells == PL_PIN_CELLS(0),
                "canonical PIN appeared in a moving heap");
      pl_val target = pl_pin_proxy_target(scan);
      if (target == 0) {
        /* The body is the proxy's only live edge until Save publishes a
         * canonical target. */
        pl_val* body = (pl_val*)&scan[5];
        *body = pl_forward(gc, *body);
      } else {
        /* Resolved targets are canonical store PINs.  Check that forwarding
         * treats the target as terminal, then discard the obsolete heap-body
         * edge so it is not retained by this collection. */
        ax_assume(gc->h->store != NULL && pl_tag(target) == PL_TAG_PIN &&
                      pl_store_owns(gc->h->store, target),
                  "resolved PIN proxy target is not store-resident");
        pl_val stable = pl_forward(gc, target);
        ax_assume(stable == target,
                  "resolved PIN proxy target moved during collection");
        scan[5] = 0;
        pl_pin_set_target(scan, stable);
      }
      scan += cells;
      continue;
    }
    default:
      ax_abort("cheney_scan: bad kind %d", (int)kind);
    }
    for (uint32_t i = first; i < first + count; i++) {
      pl_val* f = (pl_val*)&scan[i];
      *f = pl_forward(gc, *f);
    }
    scan += cells;
  }
}

static void pl_thread_roots(pl_root_visit visit, void* gc_ctx, void* src_ctx);

/* An update target is needed only if another root can still observe that
 * thunk. Keeping it alive solely to memoize a result nobody can read retains
 * every suspended tail call in a long-lived actor. Run after the strong graph
 * has been completely evacuated: shared blackholes (including their retry
 * environments) have forwarding pointers; unobserved targets may disappear.
 * This does not drop shared updates or redirect partially executed effects. */
static pl_val pl_live_update_target(pl_gc_ctx* gc, pl_val value) {
  if (value == 0)
    return 0;
  if (gc->h->store != NULL && pl_store_owns(gc->h->store, value))
    return value;
  pl_cell* p = pl_ptr(value);
  return pl_hdr_kind(p[0]) == PL_K_FWD ? (pl_val)p[1] : 0;
}

static void pl_collect_update_targets(pl_gc_ctx* gc, pl_thread* t) {
  size_t out = 0;
  for (size_t i = 0; i < t->fsp; i++) {
    pl_frame* fr = &t->fstack[i];
    if (fr->kind != PL_F_UPD)
      continue;
    uint32_t previous_count = fr->argc;
    size_t previous_base = fr->argbase;
    pl_val first = pl_live_update_target(gc, fr->a);
    uint32_t count = first != 0;
    size_t start = out;
    for (uint32_t j = 1; j < previous_count; j++) {
      pl_val value = pl_live_update_target(gc, t->ustack[previous_base + j - 1]);
      if (value == 0)
        continue;
      if (count == 0)
        first = value;
      else
        t->ustack[out++] = value;
      count++;
    }
    fr->a = first;
    fr->argbase = (uint32_t)start;
    fr->argc = count;
  }
  t->usp = out;
}

static void pl_collect_into(pl_thread* t, pl_heap* h, pl_cell* target) {
#ifndef PL_CACHE_STATS
  (void)t;
#endif
#ifndef NDEBUG
  ax_assume(h->forbid_depth == 0, "collection inside a no-collect window (I1)");
#endif
  pl_gc_ctx gc = {.h = h,
                  .target = target,
                  .target_free = target
#ifdef PL_CACHE_STATS
                  ,
                  .thread = t
#endif
  };
#ifdef PL_CACHE_STATS
  t->cache_stats.gc_collections++;
#endif
  for (size_t i = 0; i < h->nroots; i++)
    h->roots[i].fn(pl_gc_visit, &gc, h->roots[i].ctx);
  pl_cheney_scan(&gc);
  for (size_t i = 0; i < h->nroots; i++)
    if (h->roots[i].fn == pl_thread_roots)
      pl_collect_update_targets(&gc, h->roots[i].ctx);
  h->live_cells = (size_t)(gc.target_free - target);
  h->free = gc.target_free;
}

static void pl_gc_collect(pl_thread* t, pl_heap* h) {
  pl_space_reuse(h->to, h->cells);
  pl_collect_into(t, h, h->to);
  pl_cell* old_from = h->from;
  h->from = h->to;
  h->to = old_from;
  h->limit = h->from + h->cells;
  /* Every reachable moving object has been evacuated. The other semispace
   * is scratch for the next collection, not retained application memory. */
  pl_space_discard(h->to, h->cells);
}

static void pl_gc_grow(pl_thread* t, pl_heap* h, size_t need_cells) {
  size_t old_cells = h->cells;
  size_t want = h->cells;
  while (want < h->live_cells + need_cells + (h->live_cells / 2) + 4096)
    want *= 2;
  pl_cell* nfrom = pl_space_alloc(want);
  pl_cell* nto = pl_space_alloc(want);
  /* live data currently sits in h->from; evacuate it into nfrom */
  pl_cell* old_from = h->from;
  pl_cell* old_to = h->to;
  pl_collect_into(t, h, nfrom);
  h->from = nfrom;
  h->to = nto;
  h->cells = want;
  h->limit = h->from + want;
  pl_space_free(old_from, old_cells);
  pl_space_free(old_to, old_cells);
}

void pl_gc_reserve(pl_thread* t, size_t cells) {
  pl_heap* h = t->heap;
#ifdef PL_GC_STRESS
  pl_gc_collect(t, h);
#endif
  if (ax_likely(h->free + cells <= h->limit))
    return;
  pl_gc_collect(t, h);
  /* A dense surviving graph can leave enough room for this single
   * allocation while collecting again after only a few more cells.
   * Apply the grow path's existing proportional margin at collection
   * boundaries, including when the immediate allocation still fits. */
  size_t headroom = (size_t)(h->limit - h->free);
  size_t margin = h->live_cells / 2 + 4096;
  if (cells > headroom || headroom - cells < margin)
    pl_gc_grow(t, h, cells);
  ax_assume(h->free + cells <= h->limit, "heap exhausted after grow");
}

pl_cell* pl_bump(pl_thread* t, size_t cells) {
  pl_heap* h = t->heap;
  ax_assume(h->free + cells <= h->limit, "bump without reserved headroom (I2)");
  pl_cell* p = h->free;
  h->free += cells;
  return p;
}

size_t pl_gc_headroom(pl_thread* t) {
  return (size_t)(t->heap->limit - t->heap->free);
}

size_t pl_gc_live_cells(pl_heap* h) {
  return h->live_cells;
}

bool pl_gc_collect_if_pressure(pl_thread* t, size_t allocation_floor_cells) {
  pl_heap* h = t->heap;
  size_t used_cells = (size_t)(h->free - h->from);
  ax_assume(used_cells >= h->live_cells,
            "heap frontier precedes last live-set size");
  size_t allocated_cells = used_cells - h->live_cells;
  size_t threshold = h->live_cells > allocation_floor_cells
                         ? h->live_cells
                         : allocation_floor_cells;
  if (allocated_cells == 0 || allocated_cells < threshold)
    return false;
  pl_gc_collect(t, h);
  return true;
}

void pl_gc_collect_now(pl_thread* t) {
  pl_gc_collect(t, t->heap);
}

void pl_gc_trim(pl_thread* t) {
  pl_heap* h = t->heap;
  pl_gc_collect(t, h);
  size_t want = 4096;
  while (want < h->live_cells + 4096)
    want *= 2;
  if (want >= h->cells)
    return;
  size_t old_cells = h->cells;
  pl_cell* old_from = h->from;
  pl_cell* old_to = h->to;
  pl_cell* next = pl_space_alloc(want);
  pl_collect_into(t, h, next);
  h->from = next;
  h->to = pl_space_alloc(want);
  h->cells = want;
  h->limit = next + want;
  pl_space_free(old_from, old_cells);
  pl_space_free(old_to, old_cells);
}

/* ── Thread ────────────────────────────────────────────────────────────── */

static _Atomic uint64_t pl_next_profile_lane = 1;

static void pl_thread_roots(pl_root_visit visit, void* gc_ctx, void* src_ctx) {
  pl_thread* t = src_ctx;
  /* pl_forward is the identity on direct nats, and stack slots and frame
   * roots are mostly nats (pl_fpush zeroes a/b): test the tag inline
   * rather than paying an indirect call per slot to learn that. */
  for (size_t i = 0; i < t->vsp; i++)
    if (!pl_is_nat63(t->vstack[i]))
      visit(&t->vstack[i], gc_ctx);
  for (size_t i = 0; i < t->fsp; i++) {
#ifdef PL_CACHE_STATS
    if ((unsigned)t->fstack[i].kind < PL_CACHE_FRAME_CAP)
      t->cache_stats.gc_frame_kinds[t->fstack[i].kind]++;
#endif
    /* THKE update targets are weak; the post-scan phase keeps only targets
     * also reachable through the actual computation or another consumer. */
    if (t->fstack[i].kind != PL_F_UPD && !pl_is_nat63(t->fstack[i].a))
      visit(&t->fstack[i].a, gc_ctx);
    if (!pl_is_nat63(t->fstack[i].b))
      visit(&t->fstack[i].b, gc_ctx);
  }
  visit(&t->exn, gc_ctx);
  visit(&t->resume_val, gc_ctx);
  visit(&t->blocked_on, gc_ctx);
  visit(&t->result, gc_ctx);
  for (size_t i = 0; i < t->profile_zone_n; i++)
    visit(&t->profile_zones[i].handle, gc_ctx);
}

pl_thread* pl_thread_new(pl_heap* h) {
  pl_thread* t = calloc(1, sizeof(*t));
  ax_assume(t != NULL, "oom");
  t->heap = h;
  t->vcap = 4096;
  t->vstack = malloc(t->vcap * sizeof(pl_val));
  t->fcap = 4096;
  t->fstack = malloc(t->fcap * sizeof(pl_frame));
  ax_assume(t->vstack != NULL && t->fstack != NULL, "oom");
#ifdef PL_CACHE_STATS
  ax_assume(pthread_once(&pl_cache_stats_once, pl_cache_stats_register) == 0,
            "pthread_once");
#endif
  t->fuel = UINT64_MAX; /* fuel is inert outside pl_thread_run */
  t->profile_next_generation = 1;
  t->profile_lane =
      atomic_fetch_add_explicit(&pl_next_profile_lane, 1, memory_order_relaxed);
  ax_assume(t->profile_lane != 0, "profile lane id exhausted");
  pl_gc_add_root_source(h, pl_thread_roots, t);
  return t;
}

void pl_thread_free(pl_thread* t) {
  if (t == NULL)
    return;
  pl_profile_thread_free(t);
#ifdef PL_CACHE_STATS
  pl_cache_stats_merge(&t->cache_stats);
#endif
  pl_gc_del_root_source(t->heap, pl_thread_roots, t);
  free(t->vstack);
  free(t->fstack);
  free(t->ustack);
  free(t);
}

void pl_vstack_grow(pl_thread* t) {
  t->vcap *= 2;
  /* frames hold vstack offsets as u32 */
  ax_assume(t->vcap <= UINT32_MAX, "vstack exceeds u32 frame offsets");
  t->vstack = realloc(t->vstack, t->vcap * sizeof(pl_val));
  ax_assume(t->vstack != NULL, "oom");
}

void pl_fstack_grow(pl_thread* t) {
  t->fcap *= 2;
  t->fstack = realloc(t->fstack, t->fcap * sizeof(pl_frame));
  ax_assume(t->fstack != NULL, "oom");
}

void pl_ustack_grow(pl_thread* t) {
  size_t next = t->ucap == 0 ? 64 : t->ucap * 2;
  ax_assume(next > t->ucap && next <= UINT32_MAX &&
                next <= SIZE_MAX / sizeof(pl_val),
            "update stack exceeds u32 frame offsets");
  t->ustack = realloc(t->ustack, next * sizeof(pl_val));
  ax_assume(t->ustack != NULL, "oom");
  t->ucap = next;
}
