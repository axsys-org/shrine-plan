#include "plan/eval.h"

#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <inttypes.h>
#include <pthread.h>
#include <string.h>

#include "axsys/assume.h"
#include "axsys/allocator.h"
#include "axsys/perf.h"
#include "internal.h"
#include "plan/build.h"
#include "plan/canon.h"
#include "plan/nat.h"
#include "plan/store.h"

static void pl_profile_pause_all(pl_thread* t);
static void pl_profile_resume_all(pl_thread* t);
static void pl_profile_drop_since_paused(pl_thread* t, uint64_t mark);

/* pl_run dispatches with computed gotos (labels-as-values), a GNU
 * extension.  Clang suppresses the diagnostic with the targeted
 * -Wno-gnu-label-as-value (Makefile); gcc has no specific flag — the
 * pedwarn only lives in the -Wpedantic bucket, so silence that for
 * this translation unit. */
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic ignored "-Wpedantic"
#endif

/* ── Errors ────────────────────────────────────────────────────────────── */

static _Thread_local char pl_msgbuf[256];

[[noreturn]] void pl_raise(pl_thread* t, pl_val v) {
  t->exn = v;
  t->exn_msg = NULL;
  if (t->handler == NULL)
    ax_abort("uncaught PLAN_EXN");
  longjmp(*t->handler, 1);
}

[[noreturn]] void pl_raise_msg(pl_thread* t, const char* msg) {
  t->exn = 0;
  t->exn_msg = msg;
  if (t->handler == NULL)
    ax_abort("uncaught PLAN error: %s", msg);
  longjmp(*t->handler, 1);
}

[[noreturn]] void pl_raise_msgf(pl_thread* t, const char* fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(pl_msgbuf, sizeof(pl_msgbuf), fmt, ap);
  va_end(ap);
  pl_raise_msg(t, pl_msgbuf);
}

static void pl_restore_thke(pl_val thke) {
  pl_cell* p = pl_ptr(thke);
  ax_assume(pl_hdr_kind(p[0]) == PL_K_THKE,
            "unwound update target is not a THKE");
  ax_assume((pl_hdr_flags(p[0]) & PL_F_HOLE) != 0,
            "unwound THKE is not blackholed");
  uint32_t flags = pl_hdr_flags(p[0]) & ~PL_F_HOLE;
  p[0] = pl_hdr_make(PL_K_THKE, flags, pl_hdr_meta(p[0]), pl_hdr_cells(p[0]));
}

/* Roll back the in-place blackholes owned by frames that an exception or
 * abandoned computation is about to discard.  Coalesced update slices are
 * suffixes of ustack, so reverse frame order also releases them in LIFO
 * order. */
static void pl_unwind_frames(pl_thread* t, size_t base) {
  ax_assume(base <= t->fsp, "frame unwind below live stack");
  for (size_t i = t->fsp; i > base; i--) {
    pl_frame* fr = &t->fstack[i - 1];
    if (fr->kind == PL_F_PURE) {
      if (getenv("PLAN_PURE_STATS") != NULL)
        fprintf(stderr, "[pure] unwind depth=%u remaining=%llu\n",
                t->pure_depth, (unsigned long long)t->pure_remaining);
      t->pure_remaining += fr->argc;
      t->pure_depth = fr->k;
      continue;
    }
    if (fr->kind == PL_F_UPDATE) {
      pl_cell* p = pl_ptr(fr->a);
      ax_assume(pl_hdr_kind(p[0]) == PL_K_BH,
                "unwound legacy thunk is not blackholed");
      p[0] = pl_hdr_make(PL_K_THUNK, pl_hdr_flags(p[0]), pl_hdr_meta(p[0]),
                         pl_hdr_cells(p[0]));
      p[2] = fr->b;
      continue;
    }
    if (fr->kind != PL_F_UPD)
      continue;
    if (fr->argc == 0)
      continue; /* GC found no remaining observer of these update targets. */
    if (fr->argc == 1) {
      pl_restore_thke(fr->a);
      continue;
    }
    ax_assume(fr->argc >= 2 && (size_t)fr->argbase + fr->argc - 1 == t->usp,
              "coalesced update stack is not a frame suffix");
    for (size_t j = fr->argc - 1; j > 0; j--)
      pl_restore_thke(t->ustack[(size_t)fr->argbase + j - 1]);
    pl_restore_thke(fr->a);
    t->usp = fr->argbase;
  }
  t->fsp = base;
}

void pl_catch_init(pl_thread* t, pl_catch* c) {
  c->prev = t->handler;
  c->vsp = t->vsp;
  c->fsp = t->fsp;
  c->centry = t->centry_depth;
  c->profile_mark = t->profile_next_generation;
  t->handler = &c->jb;
}

void pl_catch_pop(pl_thread* t, pl_catch* c) {
  t->handler = c->prev;
}

void pl_catch_unwind(pl_thread* t, pl_catch* c) {
  t->handler = c->prev;
  pl_profile_pause_all(t);
  t->vsp = c->vsp;
  pl_unwind_frames(t, c->fsp);
  pl_profile_drop_since_paused(t, c->profile_mark);
  t->centry_depth = c->centry; /* longjmp skipped the region epilogues */
  if (t->centry_depth > 0 || t->suspendable)
    pl_profile_resume_all(t);
}

/* ── Enter hook seam ───────────────────────────────────────────────────── */

static pl_enter_hook pl_hook = NULL;

void pl_set_enter_hook(pl_enter_hook hook) {
  pl_hook = hook;
}

/* ── Direct-effect interception seam ───────────────────────────────────── */

static pl_io_hook pl_io = NULL;

void pl_set_io_hook(pl_io_hook hook) {
  pl_io = hook;
}

pl_val pl_io_run(pl_thread* t, uint32_t op, size_t argbase) {
  return pl_ops[op].body(t, argbase);
}

const char* pl_io_name(uint32_t op) {
  return pl_ops[op].name_c;
}

uint32_t pl_io_argc(uint32_t op) {
  return pl_ops[op].argc;
}

/* ── KAL: non-forcing law-body operand interpretation ──────────────────── */

/*
 * kal n e expr (the reference):
 *   [N b] | b <= n  -> env slot b            (not forced; may be a thunk)
 *   [N 0, f, x]     -> deferred application  (a fresh K_THUNK)
 *   [N 0, x]        -> x                     (literal escape)
 *   otherwise       -> expr                  (literal)
 *
 * Bump-only: the caller reserves PL_THUNK_CELLS per possible call.
 * expr must be WHNF.
 */
static pl_val pl_kal1(pl_thread* t, pl_val env, pl_val expr) {
  uint32_t n = pl_env_n(pl_ptr(env)) - 1;
  if (pl_is_nat63(expr)) {
    if (expr <= n)
      return pl_env_slots(pl_ptr(env))[expr];
    return expr;
  }
  pl_cell* p = pl_as(PL_TAG_APP, expr);
  if (p != NULL && pl_app_head(p) == 0) {
    uint32_t na = pl_app_n(p);
    if (na == 1)
      return pl_app_args(p)[0];
    if (na == 2)
      return pl_mk_thunk(t, env, expr);
  }
  return expr;
}

/* Law object behind a head value that is a LAW or a pinned LAW. */
static pl_cell* pl_lawp(pl_val head) {
  if (pl_tag(head) == PL_TAG_LAW)
    return pl_ptr(head);
  return pl_ptr(pl_pin_body(pl_ptr(head)));
}

/* Compiled bytecode for a law head, cached on its pin (NULL for an
 * unpinned law or an uncompiled pin). */
static pl_code* pl_law_code(pl_val law) {
  pl_cell* p = pl_as(PL_TAG_PIN, law);
  return p != NULL ? (pl_code*)pl_pin_code(p) : NULL;
}

/* A law compiled with a checked prologue has two entries: the prologue
 * forces the strict arguments in order and stacks the values; the fast
 * entry (past OP_ENTRY) stacks the arguments as they are.  Enter fast
 * exactly when every strict argument already is a value, looking through
 * indirections (resolved in place, so the fast entry's pushes see values
 * too).  No caller hint is trusted: this check is what lets ingest treat
 * the strict variables as WHNF at strict_entry.  args indexes the first
 * argument on the value stack; argc is the law's arity. */
static uint32_t pl_strict_entry(pl_thread* t, const pl_code* code, size_t args,
                                uint32_t argc) {
  uint64_t mask = code->strict_mask;
  if (mask == 0 || (argc < 64 && (mask >> argc) != 0))
    return 0; /* no prologue, or a mask naming arguments the law lacks */
  do {
    unsigned i = (unsigned)__builtin_ctzll(mask);
    pl_val v = t->vstack[args + i];
    if (!pl_is_whnf(v)) {
      v = pl_resolve(v);
      if (!pl_is_whnf(v))
        return 0;
      t->vstack[args + i] = v;
    }
    mask &= mask - 1;
  } while (mask != 0);
  return code->strict_entry;
}

/* ── Tracy law attribution ─────────────────────────────────────────────── */

#ifdef TRACY_ENABLE
#define PL_TRACY_DEFAULT_LAW_SAMPLE_RATE UINT64_C(1)

static pthread_once_t pl_profile_sample_once = PTHREAD_ONCE_INIT;
static uint64_t pl_profile_law_sample_rate = PL_TRACY_DEFAULT_LAW_SAMPLE_RATE;
static _Thread_local uint64_t pl_profile_law_sample_countdown;

static void pl_profile_sample_init(void) {
  const char* sample_c = getenv("ENKI_TRACY_LAW_SAMPLE_RATE");
  if (sample_c == NULL || sample_c[0] == '\0' || sample_c[0] == '-')
    return;
  char* end;
  errno = 0;
  unsigned long long sample = strtoull(sample_c, &end, 10);
  if (errno == 0 && end != sample_c && *end == '\0')
    pl_profile_law_sample_rate = (uint64_t)sample;
}

static bool pl_profile_law_sample(void) {
  ax_assume(pthread_once(&pl_profile_sample_once, pl_profile_sample_init) == 0,
            "pthread_once");
  if (pl_profile_law_sample_rate == 0)
    return false;
  if (pl_profile_law_sample_countdown == 0) {
    pl_profile_law_sample_countdown = pl_profile_law_sample_rate - 1;
    return true;
  }
  pl_profile_law_sample_countdown--;
  return false;
}

static size_t pl_profile_append(char* buf, size_t pos, size_t cap,
                                const char* s) {
  if (pos >= cap)
    return pos;
  size_t n = strlen(s);
  size_t avail = cap - pos - 1;
  if (n > avail)
    n = avail;
  memcpy(buf + pos, s, n);
  pos += n;
  buf[pos] = '\0';
  return pos;
}

static size_t pl_profile_law_name(pl_cell* lp, char* buf, size_t cap) {
  size_t pos = pl_profile_append(buf, 0, cap, "law:");
  pl_val name = pl_law_name(lp);
  bool printable = pl_is_nat(name);
  size_t n = printable ? pl_nat_byte_len(name) : 0;
  if (n == 0)
    printable = false;
  for (size_t i = 0; printable && i < n; i++) {
    uint8_t b = pl_nat_byte_at(name, i);
    if (b < 0x20 || b > 0x7e)
      printable = false;
  }

  if (printable) {
    size_t room = cap > pos + 24 ? cap - pos - 24 : 0;
    for (size_t i = 0; i < n && i < room; i++)
      buf[pos++] = (char)pl_nat_byte_at(name, i);
    buf[pos] = '\0';
    if (n > room)
      pos = pl_profile_append(buf, pos, cap, "...");
  } else {
    pos = pl_profile_append(buf, pos, cap, "<anon>");
  }

  int wrote = snprintf(buf + pos, cap - pos, "/%" PRIu64, pl_law_arity(lp));
  if (wrote > 0)
    pos += (size_t)wrote < cap - pos ? (size_t)wrote : cap - pos - 1;
  return pos;
}

static void pl_profile_frame_begin(pl_frame* fr) {
  char name[160];
  size_t name_s = 0;
  bool emit = pl_tag(fr->a) == PL_TAG_PIN && TracyCIsConnected &&
              pl_profile_law_sample();
  if (emit)
    name_s = pl_profile_law_name(pl_lawp(fr->a), name, sizeof(name));
  AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME_ACTIVE(fr->profile_ctx, name, name_s,
                                            emit);
  fr->profile_live = true;
}

static void pl_profile_frame_end(pl_frame* fr) {
  if (fr->kind == PL_F_PROF && fr->profile_live) {
    AX_PROFILE_ZONE_END(fr->profile_ctx);
    fr->profile_live = false;
  }
}

static bool pl_profile_law_push(pl_thread* t, pl_val head) {
  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_PROF;
  fr->a = head;
  pl_profile_frame_begin(fr);
  return true;
}

static void pl_profile_close_above(pl_thread* t, size_t base) {
  for (size_t i = t->fsp; i > base; i--)
    pl_profile_frame_end(&t->fstack[i - 1]);
}

static void pl_profile_reopen_above(pl_thread* t, size_t base) {
  for (size_t i = base; i < t->fsp; i++) {
    pl_frame* fr = &t->fstack[i];
    if (fr->kind == PL_F_PROF && !fr->profile_live)
      pl_profile_frame_begin(fr);
  }
}

#else
static void pl_profile_frame_end(pl_frame* fr) {
  (void)fr;
}

static bool pl_profile_law_push(pl_thread* t, pl_val head) {
  (void)t;
  (void)head;
  return false;
}

static void pl_profile_close_above(pl_thread* t, size_t base) {
  (void)t;
  (void)base;
}

static void pl_profile_reopen_above(pl_thread* t, size_t base) {
  (void)t;
  (void)base;
}
#endif

/* A fused tail call replaces the current law invocation.  Drop its profiling
 * boundary together with the execution frame so tail recursion remains
 * constant-space even when Tracy attribution is enabled. */
static void pl_profile_tail_pop(pl_thread* t) {
  if (t->fsp == 0)
    return;
  pl_frame* fr = &t->fstack[t->fsp - 1];
  if (fr->kind != PL_F_PROF)
    return;
  pl_profile_frame_end(fr);
  t->fsp--;
}

/* ── Explicit SPLAN profiling zones ───────────────────────────────────── */

static _Thread_local uint64_t pl_profile_active_lane;

uint64_t pl_profile_current_lane(void) {
  return pl_profile_active_lane;
}

static bool pl_profile_physical_enabled(void) {
#ifdef TRACY_ENABLE
  return true;
#else
  return ax_profile_json_enabled();
#endif
}

static void pl_profile_json_name_thread(pl_thread* t) {
  if (!ax_profile_json_enabled() || t->profile_json_named)
    return;
  char name[64];
  int n = snprintf(name, sizeof(name), "PLAN thread %" PRIu64, t->profile_lane);
  if (n < 0)
    return;
  size_t name_n = (size_t)n < sizeof(name) ? (size_t)n : sizeof(name) - 1;
  ax_profile_json_thread_name(t->profile_lane, name, name_n);
  t->profile_json_named = true;
}

static void pl_profile_zone_begin(pl_thread* t, pl_profile_zone* zone) {
  if (zone->live || !pl_profile_physical_enabled())
    return;
#ifdef TRACY_ENABLE
  AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME(zone->tracy_ctx, (const char*)zone->name,
                                     zone->name_n);
#endif
  if (ax_profile_json_enabled()) {
    pl_profile_json_name_thread(t);
    ax_profile_json_zone_begin(t->profile_lane, zone->generation, zone->name,
                               zone->name_n);
  }
  zone->live = true;
}

static void pl_profile_zone_end(pl_thread* t, pl_profile_zone* zone) {
  if (!zone->live)
    return;
  if (ax_profile_json_enabled())
    ax_profile_json_zone_end(t->profile_lane, zone->generation, zone->name,
                             zone->name_n);
#ifdef TRACY_ENABLE
  AX_PROFILE_ZONE_END(zone->tracy_ctx);
#endif
  zone->live = false;
}

static void pl_profile_pause_all(pl_thread* t) {
  /* Explicit zones are always outside law-attribution zones. */
  pl_profile_close_above(t, 0);
  for (size_t i = t->profile_zone_n; i > 0; i--)
    pl_profile_zone_end(t, &t->profile_zones[i - 1]);
}

static void pl_profile_resume_all(pl_thread* t) {
  for (size_t i = 0; i < t->profile_zone_n; i++)
    pl_profile_zone_begin(t, &t->profile_zones[i]);
  pl_profile_reopen_above(t, 0);
}

static void pl_profile_zone_release(pl_profile_zone* zone) {
  free(zone->name);
  *zone = (pl_profile_zone){0};
}

/* The zone list remains in generation order even after non-LIFO removals, so
 * every zone created since a catch/run watermark is a suffix. */
static void pl_profile_drop_since_paused(pl_thread* t, uint64_t mark) {
  while (t->profile_zone_n > 0 &&
         t->profile_zones[t->profile_zone_n - 1].generation >= mark) {
    pl_profile_zone_release(&t->profile_zones[t->profile_zone_n - 1]);
    t->profile_zone_n--;
  }
}

void pl_profile_thread_free(pl_thread* t) {
  pl_profile_pause_all(t);
  while (t->profile_zone_n > 0) {
    pl_profile_zone_release(&t->profile_zones[t->profile_zone_n - 1]);
    t->profile_zone_n--;
  }
  free(t->profile_zones);
  t->profile_zones = NULL;
  t->profile_zone_cap = 0;
}

static void pl_profile_zone_grow(pl_thread* t) {
  if (t->profile_zone_n < t->profile_zone_cap)
    return;
  size_t next = t->profile_zone_cap == 0 ? 8 : t->profile_zone_cap * 2;
  ax_assume(next > t->profile_zone_cap &&
                next <= SIZE_MAX / sizeof(*t->profile_zones),
            "profile zone stack overflow");
  pl_profile_zone* zones =
      realloc(t->profile_zones, next * sizeof(*t->profile_zones));
  ax_assume(zones != NULL, "oom");
  t->profile_zones = zones;
  t->profile_zone_cap = next;
}

pl_val pl_op83_zone_start(pl_thread* t, size_t ab) {
  pl_val label = t->vstack[ab];
  if (!pl_is_nat(label))
    pl_raise_msg(t, "ZoneStart: expected nat label");
  if (t->profile_next_generation > PL_NAT63_MAX)
    pl_raise_msg(t, "ZoneStart: handle space exhausted");

  size_t name_n = pl_nat_byte_len(label);
  uint8_t* name = malloc(name_n == 0 ? 1 : name_n);
  ax_assume(name != NULL, "oom");
  for (size_t i = 0; i < name_n; i++)
    name[i] = pl_nat_byte_at(label, i);

  pl_profile_zone_grow(t);
  uint64_t generation = t->profile_next_generation;
  pl_val handle_arg = generation;
  pl_gc_reserve(t, PL_APP_CELLS(1));
  PL_GC_FORBID(t);
  pl_val handle = pl_mk_app_from(t, 0, 1, &handle_arg);
  PL_GC_ALLOW(t);

  /* Re-parent the currently live law zones beneath the new explicit zone. */
  pl_profile_close_above(t, 0);
  pl_profile_zone* zone = &t->profile_zones[t->profile_zone_n++];
  *zone = (pl_profile_zone){
      .handle = handle,
      .name = name,
      .name_n = name_n,
      .generation = generation,
  };
  t->profile_next_generation++;
  pl_profile_zone_begin(t, zone);
  pl_profile_reopen_above(t, 0);
  return handle;
}

pl_val pl_op83_zone_end(pl_thread* t, size_t ab) {
  pl_val handle = t->vstack[ab];
  size_t found = t->profile_zone_n;
  for (size_t i = 0; i < t->profile_zone_n; i++) {
    if (t->profile_zones[i].handle == handle) {
      found = i;
      break;
    }
  }
  if (found == t->profile_zone_n)
    pl_raise_msg(t, "ZoneEnd: invalid handle");

  /* Tracy and Chrome B/E events are properly nested.  Temporarily close
   * younger zones when removing an older handle, then reopen the survivors. */
  pl_profile_close_above(t, 0);
  for (size_t i = t->profile_zone_n; i > found; i--)
    pl_profile_zone_end(t, &t->profile_zones[i - 1]);
  pl_profile_zone_release(&t->profile_zones[found]);
  if (found + 1 < t->profile_zone_n) {
    memmove(&t->profile_zones[found], &t->profile_zones[found + 1],
            (t->profile_zone_n - found - 1) * sizeof(*t->profile_zones));
  }
  t->profile_zone_n--;
  for (size_t i = found; i < t->profile_zone_n; i++)
    pl_profile_zone_begin(t, &t->profile_zones[i]);
  pl_profile_reopen_above(t, 0);
  return 0;
}

/* ── Suspension slow path ──────────────────────────────────────────────── */

/*
 * Called when the per-step fuel decrement hits zero.  Returns true when
 * the machine should capture a resume point and yield: only under
 * pl_thread_run, and only with no native frames between the trampoline
 * and the current step — returning would abandon live C state.
 * Otherwise the request is deferred: under an executor, fuel is pinned
 * to 1 so every subsequent step funnels back here until depth 0 (the
 * grace path); outside an executor fuel is inert and simply rearmed.
 */
/* A stack-resident law entry (PL_F_EXECV, or a block-call frame
 * inheriting its group) defers the env build; the first operation
 * that actually captures an env — MK_THK, INTERP, x_tail's thunk
 * fallback — reifies one here.  Idempotent; reads keep hitting the
 * stack copies. */
static void pl_exec_reify_env(pl_thread* t, pl_frame* fr) {
  if (fr->a != 0 || fr->argc == 0)
    return;
  uint32_t n = fr->argc;
  pl_gc_reserve(t, PL_ENV_CELLS(n));
  PL_GC_FORBID(t);
  pl_val envv = pl_mk_env_uninit(t, n);
  pl_val* slots = pl_env_slots(pl_ptr(envv));
  for (uint32_t i = 0; i < n; i++)
    slots[i] = t->vstack[(size_t)fr->b + i];
  fr->a = envv;
  PL_GC_ALLOW(t);
}

static bool pl_yield_now(pl_thread* t) {
  if (t->suspendable && t->centry_depth == 0) {
    t->pending_yield = false;
    return true;
  }
  if (t->suspendable) {
    t->pending_yield = true;
    t->fuel = 1;
  } else {
    t->fuel = UINT64_MAX;
  }
  return false;
}

/* Consecutive THKE updates all receive the same result.  Keep the common
 * singleton in its ordinary frame; on the second update, turn that frame into
 * a marker for a dense ustack suffix and append subsequent targets there. */
static void pl_push_thke_update(pl_thread* t, size_t base, pl_val thke) {
  if (t->fsp > base) {
    pl_frame* fr = &t->fstack[t->fsp - 1];
    if (fr->kind == PL_F_UPD) {
      ax_assume(fr->argc < UINT32_MAX, "update chain is too large");
      if (fr->argc == 0) {
        fr->a = thke;
        fr->argc = 1;
      } else if (fr->argc == 1) {
        size_t start = t->usp;
        pl_upush(t, thke);
        fr->argbase = (uint32_t)start;
        fr->argc = 2;
      } else {
        ax_assume(fr->argc >= 2 && (size_t)fr->argbase + fr->argc - 1 == t->usp,
                  "coalesced update stack is not a frame suffix");
        pl_upush(t, thke);
        fr->argc++;
      }
      pl_cache_stat_upd_push(t, fr->argc);
      return;
    }
  }

  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_UPD;
  fr->a = thke;
  fr->argc = 1;
  pl_cache_stat_upd_push(t, 1);
}

/* ── The machine ───────────────────────────────────────────────────────── */

static pl_run_status pl_run_caught(pl_thread* t, pl_val v0, size_t base,
                                   uint8_t entry0);

/* entry is a pl_resume_kind: EVAL evaluates v, RETURN delivers v to the
 * top frame, RUN re-enters compiled code at the top F_EXEC frame's
 * saved offset (v is unused). */
static pl_run_status pl_run(pl_thread* t, pl_val v, size_t base,
                            uint8_t entry) {
  pl_val env, expr;
  pl_frame* fr;
  size_t hbase = 0;
  uint32_t argc = 0;
  /* JUDGE scan coordinates; restored from the F_JUDGE frame on resume
   * (offsets only — the chain itself lives on the value stack) */
  size_t jbase = 0;
  uint32_t jargc = 0;
  uint32_t op_idx, op_argc;
  size_t op_base;

  /*
   * Computed-goto dispatch tables (labels-as-values; the Makefile
   * carries -Wno-gnu-label-as-value for exactly this).  Frames keep
   * their kind byte — the host pushes frames from outside this
   * function, the TRY scan and the profiler read kinds, and the GC
   * traces a/b regardless — so dispatch is one indexed load here
   * rather than a label stored in the frame.
   */
  static void* const defer_tbl[PL_K_THKE + 1] = {
      [PL_K_THUNK] = &&defer_thunk,
      [PL_K_IND] = &&defer_ind,
      [PL_K_BH] = &&defer_bh,
      [PL_K_THKE] = &&defer_thke,
  };
  /* OP_TAILCALL is never emitted by the compiler — the ingest walker
   * fuses MK_THK+RET into it. */
  static void* const op_tbl[PL_OP_COUNT] = {
      [OP_PUSH_VAR] = &&x_push_var,
      [OP_PUSH_LIT] = &&x_push_lit,
      [OP_MK_THK] = &&x_mk_thk,
      [OP_MK_APP] = &&x_mk_app,
      [OP_INTERP] = &&x_interp,
      [OP_RET] = &&x_ret,
      [OP_FORCE] = &&x_force,
      [OP_FORCE_READY] = &&x_force_ready,
      [OP_RET_READY] = &&x_ret_ready,
      [OP_CALL_READY] = &&x_call_known,
      [OP_TAIL_READY] = &&x_tail,
      [OP_CALL] = &&x_call,
      [OP_TAILCALL] = &&x_tail,
      [OP_PUSH_SLOT] = &&x_push_slot,
      [OP_BR] = &&x_br,
      [OP_JMP] = &&x_jmp,
      [OP_ENTRY] = &&x_entry,
      [OP_CALL_KNOWN] = &&x_call_known,
      [OP_ADD] = &&x_add,
      [OP_SUB] = &&x_sub,
      [OP_CMP] = &&x_cmp,
      [OP_TAIL_ADD] = &&x_tail_add,
      [OP_TAIL_SUB] = &&x_tail_sub,
      [OP_TAIL_CMP] = &&x_tail_cmp,
      [OP_CALL_FAST] = &&x_call_fast,
      [OP_CALL_SLOW] = &&x_call_slow,
      [OP_NOP] = &&x_nop,
  };
  static void* const ret_tbl[PL_F_KIND_COUNT] = {
      [PL_F_UPDATE] = &&ret_update, [PL_F_APPLY] = &&ret_apply,
      [PL_F_SEQ] = &&ret_seq,       [PL_F_KAL] = &&ret_kal,
      [PL_F_KAPP] = &&ret_kapp,     [PL_F_OPENT] = &&ret_opent,
      [PL_F_OPARG] = &&ret_oparg,   [PL_F_OPDEEP] = &&ret_opdeep,
      [PL_F_NF] = &&ret_nf,         [PL_F_NFOBJ] = &&ret_nfobj,
      [PL_F_EXEC] = &&ret_exec,     [PL_F_EXECV] = &&ret_exec,
      [PL_F_UPD] = &&ret_upd,       [PL_F_TRY] = &&ret_try,
      [PL_F_JUDGE] = &&ret_judge,   [PL_F_NIL] = &&ret_nil,
      [PL_F_PROF] = &&ret_prof,     [PL_F_APPLYN] = &&ret_applyn,
      [PL_F_MEMO] = &&ret_memo, [PL_F_PURE] = &&ret_pure,
  };

  if (entry == PL_RES_RETURN)
    goto ret;
  if (entry == PL_RES_RUN)
    goto exec;

eval:
  if (ax_unlikely(t->pure_depth != 0)) {
    if (t->pure_remaining == 0) pl_raise_msg(t, "Pure: evaluation budget exhausted");
    t->pure_remaining--;
  }
  /*
   * The per-step safepoint: one decrement and one branch.  Fuel is the
   * only yield trigger.  At this position the complete machine
   * state is (v, value stack, frame stack) — nothing lives in C locals —
   * so suspension is a two-field capture and a normal return.
   */
  if (ax_unlikely(--t->fuel == 0) && pl_yield_now(t)) {
    t->resume_kind = PL_RES_EVAL;
    t->resume_val = v;
    pl_profile_pause_all(t);
    return PL_RUN_YIELDED;
  }
  if (pl_is_whnf(v))
    goto ret;
  {
    /* the kind is a raw 8-bit header field: bound it before indexing */
    pl_kind k = pl_hdr_kind(*pl_ptr(v));
    if (ax_unlikely(k > PL_K_THKE || defer_tbl[k] == NULL))
      ax_abort("EVAL: bad defer kind");
    goto* defer_tbl[k];
  }

  /* each label re-derives its cell pointer from v: pl_ptr is a mask,
   * and computed-goto targets can't share locals — gcc assumes any
   * goto* may reach any address-taken label (-Wmaybe-uninitialized) */
defer_ind:
  v = pl_ind_target(pl_ptr(v));
  goto eval;

defer_bh:
  pl_raise_msg(t, "<<loop>>");

defer_thunk: {
  pl_cell* p = pl_ptr(v);
  env = pl_thunk_env(p);
  expr = pl_thunk_expr(p);
  /* blackhole; the F_UPDATE frame writes the result back */
  p[0] = pl_hdr_make(PL_K_BH, pl_hdr_flags(p[0]), pl_hdr_meta(p[0]),
                     pl_hdr_cells(p[0]));
  p[2] = 0;
  fr = pl_fpush(t);
  fr->kind = PL_F_UPDATE;
  fr->a = v;
  fr->b = expr; /* retained so exceptional unwind can restore the thunk */
  goto eval_expr;
}

defer_thke: {
  pl_cell* p = pl_ptr(v);
  if (pl_thke_bane(p) & PL_BAN_NOUPD)
    goto eval_thke_v; /* Zero/Once entry count: no blackhole, no update
                         frame; re-entry re-evaluates */
  if ((pl_hdr_flags(p[0]) & PL_F_HOLE) != 0)
    pl_raise_msg(t, "<<loop>>");
  p[0] = pl_hdr_set_flag(p[0], PL_F_HOLE);
  pl_push_thke_update(t, base, v);
  goto eval_thke_v;
}
eval_thke_v: {
  pl_val* args;
  pl_bane ban = (pl_bane)(pl_thke_bane(pl_ptr(v)) & PL_BAN_MASK);
  argc = pl_thke_n(pl_ptr(v));
  args = pl_thke_args(pl_ptr(v));
  if (argc == 0)
    pl_raise_msg(t, "bad empty bytecode thunk");
  if (ban == PL_BAN_FAST) {
    /*
     * The bane is a hint from installed (untrusted) PLAN code: verify
     * that the head really is a law (or pinned law) applied at exact
     * arity before skipping the generic apply path.  Anything else —
     * including a non-WHNF head — takes the slow path, which is
     * semantically identical.
     */
    pl_val head = args[0];
    pl_cell* lp = NULL;
    if (pl_tag(head) == PL_TAG_LAW)
      lp = pl_ptr(head);
    else if (pl_tag(head) == PL_TAG_PIN &&
             pl_tag(pl_pin_body(pl_ptr(head))) == PL_TAG_LAW)
      lp = pl_ptr(pl_pin_body(pl_ptr(head)));
    if (lp == NULL || pl_law_arity(lp) != argc - 1)
      goto thke_slow;
    hbase = t->vsp;
    for (uint32_t i = 0; i < argc; i++)
      pl_vpush(t, args[i]);
    argc--;
    goto judge;
  }
  if (ban == PL_BAN_PRIM_KNOWN) {
    /* [opidx, e1..en]: ingest already resolved the op — no row, no
     * F_OPENT, no lookup; enter the strict-arg driver directly */
    uint32_t idx = (uint32_t)args[0];
    assert(idx < pl_nops);
    if (pl_ops[idx].opset >= 82 && !t->rplan_f)
      pl_raise_msg(t, "Not in RPLAN Mode"); /* the F_OPENT gate */
    size_t listbase = t->vsp;
    for (uint32_t i = 0; i < argc; i++)
      pl_vpush(t, args[i]); /* idx fills the name slot: op_body's
                               vsp = argbase - 1 drops it as usual */
    op_idx = idx;
    op_base = listbase + 1;
    op_argc = argc - 1;
    goto op_args;
  }
  if (ban == PL_BAN_PRIM) {
    /* [oppin, arg]: dispatch straight into the primop entry, exactly
     * as fast_apply's pinned-nat case would after re-unwinding */
    pl_cell* pp;
    if (argc != 2 || (pp = pl_as(PL_TAG_PIN, args[0])) == NULL ||
        !pl_is_nat(pl_pin_body(pp)))
      goto thke_slow;
    fr = pl_fpush(t);
    fr->kind = PL_F_OPENT;
    fr->opset = pl_nat_u64_clamp(pl_pin_body(pp));
    v = args[1];
    goto eval;
  }
  if (ax_unlikely(ban != PL_BAN_SLOW))
    ax_abort("EVAL: bad bane");
thke_slow:
  /* [f, p1..pm]: park the pending args on the vstack under a single
   * F_APPLYN frame; once the head is WHNF its arity decides the whole
   * application in one step (ret_applyn) — no per-arg frames, no
   * intermediate partial apps */
  if (argc == 1) { /* bare head: just force it */
    v = args[0];
    goto eval;
  }
  {
    size_t appbase = t->vsp;
    pl_vpush(t, 0); /* head slot, filled at ret_applyn */
    for (uint32_t i = 1; i < argc; i++)
      pl_vpush(t, args[i]);
    fr = pl_fpush(t);
    fr->kind = PL_F_APPLYN;
    fr->argbase = (uint32_t)(appbase + 1);
    fr->argc = argc - 1;
    v = args[0];
    goto eval;
  }
}

exec: {
  /*
   * Threaded bytecode dispatch: each handler ends in its own indirect
   * branch through op_tbl.  The installed compiler is trusted, so the
   * fetch and opcode bounds checks are debug-only; op_tbl has an entry
   * for every opcode below PL_OP_COUNT, so no handler-NULL check is
   * needed here (pass 1 of the decoder rejects anything else).
   */
#define NEXT() (assert(fr->k < fr->code->nops), fr->code->ops[fr->k++])
#define DISPATCH()                                                             \
  do {                                                                         \
    if (ax_unlikely(t->pure_depth != 0)) {                                     \
      if (t->pure_remaining == 0)                                              \
        pl_raise_msg(t, "Pure: evaluation budget exhausted");                   \
      t->pure_remaining--;                                                    \
    }                                                                         \
    pl_op_t op_ = NEXT();                                                      \
    assert(op_ < PL_OP_COUNT);                                                 \
    goto* op_tbl[op_];                                                         \
  } while (0)
  fr = &t->fstack[t->fsp - 1];
  DISPATCH();

x_push_var: {
  pl_op_t slot = NEXT();
  if (fr->argc != 0) {
    /* stack-resident group: vars live at [b, b+argc) on the vstack
     * (reification copies them into an env for capture, but reads
     * keep hitting the stack — the values are identical) */
    if (slot >= fr->argc)
      pl_raise_msg(t, "exec: variable out of range");
    pl_vpush(t, t->vstack[(size_t)fr->b + slot]);
    DISPATCH();
  }
  if (slot >= pl_env_n(pl_ptr(fr->a)))
    pl_raise_msg(t, "exec: variable out of range");
  pl_vpush(t, pl_env_slots(pl_ptr(fr->a))[slot]);
  DISPATCH();
}

x_push_lit:
  pl_vpush(t, NEXT());
  DISPATCH();

x_mk_thk: {
  /* No reify: bytecode thunks capture their executable argument vector,
   * not the activation environment. */
  argc = (uint32_t)NEXT();
  pl_op_t rawbane = NEXT();
  pl_bane bane = (pl_bane)(rawbane & PL_BAN_MASK);
  if (argc == 0 || argc > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  if (bane == PL_BAN_PRIM_KNOWN) {
    /* two extra operands: the op index (resolved at ingest from the
     * emitted opset pin + name) and the speculation code */
    uint32_t idx = (uint32_t)NEXT();
    pl_op_t spec = NEXT();
    if (spec != PL_SPEC_NONE) {
      /* Cheap eagerness: a total O(1) nat primop whose arguments are
       * already direct nats computes to the same value whenever it is
       * forced, so compute it now instead of allocating a thunk that
       * would be entered, blackholed and updated later.  Indirections
       * left by earlier forces are looked through; anything unevaluated
       * or big keeps the thunk. */
      pl_val* a = pl_vpeek(t, argc);
      if (spec == PL_SPEC_BODY) {
        /* A total, allocation-free field read (row projection or value
         * inspection): once every strict operand is a value (indirections
         * resolved in place), run the body itself instead of building a
         * thunk to run it later.  The result may be an unevaluated
         * element; it stands in for the projection thunk exactly. */
        const pl_opdesc* d = &pl_ops[idx];
        bool ready = true;
        for (uint32_t k = 0; ready && k < argc; k++) {
          if (((d->strict_mask >> k) & 1u) == 0)
            continue;
          pl_val w = a[k];
          if (!pl_is_whnf(w)) {
            w = pl_resolve(w);
            if (pl_is_whnf(w))
              a[k] = w;
            else
              ready = false;
          }
        }
        if (ready) {
          pl_val r = d->body(t, t->vsp - argc);
          pl_vreplace(t, argc, r);
          DISPATCH();
        }
      }
      pl_val x = pl_resolve(a[0]);
      pl_val y = argc > 1 ? pl_resolve(a[1]) : 0;
      if (pl_is_nat63(x) && pl_is_nat63(y)) {
        pl_val r = 0;
        bool ok = true;
        switch (spec) {
        case PL_SPEC_ADD:
          r = x + y;
          ok = pl_is_nat63(r);
          break;
        case PL_SPEC_SUB:
          r = x > y ? x - y : 0;
          break;
        case PL_SPEC_MUL: {
          uint64_t p;
          ok = !__builtin_mul_overflow(x, y, &p) && pl_is_nat63(p);
          r = p;
          break;
        }
        case PL_SPEC_INC:
          ok = x < PL_NAT63_MAX;
          r = x + 1;
          break;
        case PL_SPEC_DEC:
          r = x == 0 ? 0 : x - 1;
          break;
        case PL_SPEC_EQ:
          r = x == y;
          break;
        case PL_SPEC_NE:
          r = x != y;
          break;
        case PL_SPEC_LT:
          r = x < y;
          break;
        case PL_SPEC_LE:
          r = x <= y;
          break;
        case PL_SPEC_GT:
          r = x > y;
          break;
        case PL_SPEC_GE:
          r = x >= y;
          break;
        case PL_SPEC_CMP:
          r = x < y ? 0 : (x == y ? 1 : 2);
          break;
        case PL_SPEC_NIL:
          r = x == 0;
          break;
        case PL_SPEC_TRUTH:
          r = x != 0;
          break;
        default:
          ok = false;
          break;
        }
        if (ok) {
          pl_vreplace(t, argc, r);
          DISPATCH();
        }
      }
    }
    pl_gc_reserve(t, PL_THKE_CELLS(argc + 1));
    PL_GC_FORBID(t);
    pl_val thke = pl_mk_thke_known(t, idx, argc, pl_vpeek(t, argc));
    if (rawbane & PL_BAN_NOUPD)
      pl_ptr(thke)[1] = PL_BAN_PRIM_KNOWN | PL_BAN_NOUPD;
    pl_vreplace(t, argc, thke);
    PL_GC_ALLOW(t);
    DISPATCH();
  }
  if (bane != PL_BAN_FAST && bane != PL_BAN_SLOW && bane != PL_BAN_PRIM)
    pl_raise_msg(t, "exec: bad bane");
  pl_gc_reserve(t, PL_THKE_CELLS(argc));
  PL_GC_FORBID(t);
  pl_val thke = pl_mk_thke(t, (pl_bane)rawbane, argc, pl_vpeek(t, argc));
  pl_vreplace(t, argc, thke);
  PL_GC_ALLOW(t);
  DISPATCH();
}

x_mk_app: {
  argc = (uint32_t)NEXT();
  if (argc == 0 || argc + 1 > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  pl_gc_reserve(t, PL_APP_CELLS(argc));
  PL_GC_FORBID(t);
  size_t appbase = t->vsp - argc - 1;
  pl_val app =
      pl_mk_app_from(t, t->vstack[appbase], argc, &t->vstack[appbase + 1]);
  t->vsp = appbase;
  pl_vpush(t, app);
  PL_GC_ALLOW(t);
  DISPATCH();
}

x_interp:
  pl_exec_reify_env(t, fr);
  env = fr->a;
  expr = NEXT();
  goto eval_expr;

x_ret:
  if (t->vsp == fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  v = pl_vpop(t);
  /* a stack-resident entry owns its [head, args…] group too: the
   * result replaces the whole group, exactly where the caller's slot
   * model expects it */
  t->vsp = fr->kind == PL_F_EXECV ? (size_t)fr->b : fr->argbase;
  t->fsp--;
  if (t->fuel > 1 && pl_is_whnf(v)) {
    t->fuel--;
    goto ret;
  }
  goto eval;

x_ret_ready:
  if (t->vsp == fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  v = pl_vpop(t);
  assert(pl_is_whnf(v));
  t->vsp = fr->kind == PL_F_EXECV ? (size_t)fr->b : fr->argbase;
  t->fsp--;
  if (t->fuel > 1) {
    t->fuel--;
    goto ret;
  }
  goto eval; /* retain the canonical result checkpoint */

x_tail: {
  /*
   * MK_THK+RET fused at ingest: the thunk would be forced immediately
   * and has no other consumer, so enter the application directly at
   * the caller's frame slot — no thunk, no F_UPD, and tail recursion
   * runs in constant frame depth.  The group of n values relocates to
   * tbase, exactly where x_ret's vsp reset would have left the stack.
   */
  bool args_ready = fr->code->ops[fr->k - 1] == OP_TAIL_READY;
  argc = (uint32_t)NEXT();
  pl_op_t rawbane = NEXT();
  pl_bane bane = (pl_bane)(rawbane & PL_BAN_MASK);
  uint32_t idx = 0;
  if (bane == PL_BAN_PRIM_KNOWN) {
    idx = (uint32_t)NEXT();
    (void)NEXT();
  }
  if (argc == 0 || argc > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  if (bane != PL_BAN_FAST && bane != PL_BAN_SLOW && bane != PL_BAN_PRIM &&
      bane != PL_BAN_PRIM_KNOWN)
    pl_raise_msg(t, "exec: bad bane");
  size_t tbase = fr->kind == PL_F_EXECV ? (size_t)fr->b : fr->argbase;
  size_t g = t->vsp - argc;
  /*
   * The tail entry skips the eval: safepoint the thunk force would
   * have hit — take the fuel step here, and on exhaustion fall back
   * to the thunk so the canonical safepoint captures the yield with a
   * complete continuation (rearm to 1 so the wraparound is impossible).
   */
  if (ax_unlikely(--t->fuel == 0)) {
    t->fuel = 1;
    goto tail_fallback;
  }
  if (bane == PL_BAN_FAST) {
    pl_val head = t->vstack[g];
    pl_cell* lp = NULL;
    if (pl_tag(head) == PL_TAG_LAW)
      lp = pl_ptr(head);
    else if (pl_tag(head) == PL_TAG_PIN &&
             pl_tag(pl_pin_body(pl_ptr(head))) == PL_TAG_LAW)
      lp = pl_ptr(pl_pin_body(pl_ptr(head)));
    if (lp == NULL || pl_law_arity(lp) != argc - 1)
      goto tail_fallback; /* mis-hinted: the generic path via the thunk */
    pl_cache_stat_vstack_move(t, PL_CACHE_MOVE_TAIL_FAST,
                              (size_t)argc * sizeof(pl_val),
                              (ptrdiff_t)tbase - (ptrdiff_t)g);
    memmove(&t->vstack[tbase], &t->vstack[g], (size_t)argc * sizeof(pl_val));
    t->vsp = tbase + argc;
    t->fsp--;
    pl_profile_tail_pop(t);
    hbase = tbase;
    argc--;
    goto judge;
  }
  if (bane == PL_BAN_PRIM_KNOWN) {
    assert(idx < pl_nops);
    if (pl_ops[idx].opset >= 82 && !t->rplan_f)
      pl_raise_msg(t, "Not in RPLAN Mode");
    pl_vpush(t, 0); /* room for the name slot when g == tbase */
    pl_cache_stat_vstack_move(t, PL_CACHE_MOVE_TAIL_KNOWN,
                              (size_t)argc * sizeof(pl_val),
                              (ptrdiff_t)(tbase + 1) - (ptrdiff_t)g);
    memmove(&t->vstack[tbase + 1], &t->vstack[g],
            (size_t)argc * sizeof(pl_val));
    t->vstack[tbase] = idx; /* after the move: aliased when g == tbase */
    t->vsp = tbase + 1 + argc;
    t->fsp--;
    pl_profile_tail_pop(t);
    op_idx = idx;
    op_base = tbase + 1;
    op_argc = argc;
    if (args_ready) {
      unsigned steps = (unsigned)__builtin_popcount(pl_ops[idx].strict_mask);
      if (t->fuel > steps) {
        t->fuel -= steps;
        goto op_args_ready;
      }
    }
    goto op_args;
  }
  if (bane == PL_BAN_PRIM) {
    pl_cell* pp;
    if (argc != 2 || (pp = pl_as(PL_TAG_PIN, t->vstack[g])) == NULL ||
        !pl_is_nat(pl_pin_body(pp)))
      goto tail_fallback;
    v = t->vstack[g + 1];
    t->vsp = tbase;
    t->fsp--;
    pl_profile_tail_pop(t);
    fr = pl_fpush(t);
    fr->kind = PL_F_OPENT;
    fr->opset = pl_nat_u64_clamp(pl_pin_body(pp));
    goto eval;
  }
  /* PL_BAN_SLOW */
  if (argc == 1) { /* bare head */
    v = t->vstack[g];
    t->vsp = tbase;
    t->fsp--;
    pl_profile_tail_pop(t);
    goto eval;
  }
  v = t->vstack[g]; /* before zeroing: aliased when g == tbase */
  pl_cache_stat_vstack_move(t, PL_CACHE_MOVE_TAIL_SLOW,
                            (size_t)(argc - 1) * sizeof(pl_val),
                            (ptrdiff_t)tbase - (ptrdiff_t)g);
  memmove(&t->vstack[tbase + 1], &t->vstack[g + 1],
          (size_t)(argc - 1) * sizeof(pl_val));
  t->vstack[tbase] = 0; /* head slot for ret_applyn */
  t->vsp = tbase + argc;
  t->fsp--;
  pl_profile_tail_pop(t);
  fr = pl_fpush(t);
  fr->kind = PL_F_APPLYN;
  fr->argbase = (uint32_t)(tbase + 1);
  fr->argc = argc - 1;
  goto eval;

tail_fallback:
  /* Build the thunk after all (fuel boundary or mis-hint) and take
   * x_ret's exit: the eval: safepoint owns any yield from here.
   * This continuation is fresh and never escapes to another consumer.
   * Updating it would retain every paused tail call until the outer loop
   * returns, including old request/state graphs in long-lived actors. */
  rawbane |= PL_BAN_NOUPD;
  pl_gc_reserve(t, bane == PL_BAN_PRIM_KNOWN ? PL_THKE_CELLS(argc + 1)
                                             : PL_THKE_CELLS(argc));
  PL_GC_FORBID(t);
  pl_val thke = bane == PL_BAN_PRIM_KNOWN
                    ? pl_mk_thke_known(t, idx, argc, pl_vpeek(t, argc))
                    : pl_mk_thke(t, (pl_bane)rawbane, argc, pl_vpeek(t, argc));
  if (bane == PL_BAN_PRIM_KNOWN && (rawbane & PL_BAN_NOUPD))
    pl_ptr(thke)[1] = PL_BAN_PRIM_KNOWN | PL_BAN_NOUPD;
  PL_GC_ALLOW(t);
  v = thke;
  t->vsp = tbase;
  t->fsp--;
  pl_profile_tail_pop(t);
  goto eval;
}

x_entry:
  /* the fast-entry marker: a no-op when the checked prologue falls
   * through it (the mask operand is skipped) */
  (void)NEXT();
  DISPATCH();

x_nop:
  /* ingest filler left where a MK_THK KNOWN became a shorter CALL_KNOWN */
  DISPATCH();

x_force_ready:
  if (t->vsp == fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  assert(pl_is_whnf(t->vstack[t->vsp - 1]));
  if (t->fuel > 1) {
    t->fuel--;
    DISPATCH();
  }
  goto x_force;

x_force:
  /* pop and evaluate to WHNF; ret_exec delivers the result back onto
   * the operand stack when the value returns to this frame */
  if (t->vsp == fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  if (t->fuel > 1 && pl_is_whnf(t->vstack[t->vsp - 1])) {
    t->fuel--;
    DISPATCH();
  }
  v = pl_vpop(t);
  goto eval;

x_push_slot: {
  pl_op_t slot = NEXT();
  if (slot >= t->vsp - fr->argbase)
    pl_raise_msg(t, "exec: slot out of range");
  pl_vpush(t, t->vstack[fr->argbase + slot]);
  DISPATCH();
}

x_br: {
  /* [m, t0..t(m-1)]: the scrutinee is the (already forced) top of
   * stack; arm targets were boundary-checked at ingest.  A backward
   * arm is a loop edge: take a fuel step there, and on exhaustion
   * yield with the jump already taken (PL_RES_RUN resumes exec). */
  size_t br_pc = fr->k - 1;
  pl_op_t m = NEXT();
  if (t->vsp == fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  pl_val scrut = pl_vpop(t);
  if (!pl_is_nat63(scrut))
    pl_raise_msg(t, "exec: branch on non-nat");
  if (scrut >= m)
    pl_raise_msg(t, "exec: branch out of range");
  pl_op_t target = fr->code->ops[fr->k + scrut];
  fr->k = (uint32_t)target;
  if (target <= br_pc && ax_unlikely(--t->fuel == 0) && pl_yield_now(t)) {
    t->resume_kind = PL_RES_RUN;
    pl_profile_pause_all(t);
    return PL_RUN_YIELDED;
  }
  DISPATCH();
}

x_jmp: {
  size_t jmp_pc = fr->k - 1;
  pl_op_t target = NEXT();
  fr->k = (uint32_t)target;
  if (target <= jmp_pc && ax_unlikely(--t->fuel == 0) && pl_yield_now(t)) {
    t->resume_kind = PL_RES_RUN;
    pl_profile_pause_all(t);
    return PL_RUN_YIELDED;
  }
  DISPATCH();
}

x_call: {
  /* [target, argc]: call a local block; the argc topmost operands
   * become the callee's operand-stack base, consumed by its RET, whose
   * result arrives WHNF via ret_exec.  Every call takes a fuel step
   * (self-recursive local calls would otherwise grow the frame stack
   * unpreemptably); on exhaustion, yield rewound to re-execute the
   * call with fresh fuel. */
  size_t call_pc = fr->k - 1;
  pl_op_t target = NEXT();
  pl_op_t nargs = NEXT();
  if (nargs > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  if (ax_unlikely(--t->fuel == 0) && pl_yield_now(t)) {
    fr->k = (uint32_t)call_pc;
    t->resume_kind = PL_RES_RUN;
    pl_profile_pause_all(t);
    return PL_RUN_YIELDED;
  }
  pl_code* ccode = fr->code;
  pl_val cenv = fr->a;
  pl_val cb = fr->b;
  uint32_t cargc = fr->argc;
  fr = pl_fpush(t);
  fr->kind = PL_F_EXEC;
  fr->a = cenv;
  fr->b = cb; /* inherited stack-group base (see PL_F_EXECV) */
  fr->argc = cargc;
  fr->code = ccode;
  fr->k = (uint32_t)target;
  fr->argbase = (uint32_t)(t->vsp - nargs);
  DISPATCH();
}

/* No allocation or suspension on these paths. Leave the operands and PC
 * untouched until every guard passes, so fallback uses CALL_KNOWN verbatim.
 * Three fuel steps cover the two strict arguments and the primitive result;
 * near a checkpoint the generic path preserves its exact resumable state. */
#define NUMERIC_ARGS(fallback, steps)                                          \
  if (t->vsp - fr->argbase < 2)                                                \
    pl_raise_msg(t, "bytecode stack underflow");                               \
  pl_val x = t->vstack[t->vsp - 2];                                            \
  pl_val y = t->vstack[t->vsp - 1];                                            \
  if (!pl_is_nat63(x) || !pl_is_nat63(y) || t->fuel <= (steps)) {              \
    goto fallback;                                                             \
  }
#define NUMERIC_RETURN(result)                                                 \
  do {                                                                         \
    t->fuel -= 3;                                                              \
    t->vstack[t->vsp - 2] = (result);                                          \
    t->vsp--;                                                                  \
    fr->k += 3;                                                                \
    DISPATCH();                                                                \
  } while (0)
x_add: {
  NUMERIC_ARGS(x_call_known, 3);
  pl_val sum = x + y;
  if (!pl_is_nat63(sum))
    goto x_call_known;
  NUMERIC_RETURN(sum);
}
x_sub: {
  NUMERIC_ARGS(x_call_known, 3);
  NUMERIC_RETURN(x > y ? x - y : 0);
}
x_cmp: {
  NUMERIC_ARGS(x_call_known, 3);
  NUMERIC_RETURN(x < y ? 0 : (x == y ? 1 : 2));
}
/* Tail entries also replace the current execution frame and consume the
 * thunk-entry fuel step. Keep the original tail path for every fallback. */
#define NUMERIC_TAIL_RETURN(result)                                            \
  do {                                                                         \
    v = (result);                                                              \
    t->fuel -= 4;                                                              \
    t->vsp = fr->kind == PL_F_EXECV ? (size_t)fr->b : fr->argbase;             \
    t->fsp--;                                                                  \
    pl_profile_tail_pop(t);                                                    \
    goto ret;                                                                  \
  } while (0)
x_tail_add: {
  NUMERIC_ARGS(x_tail, 4);
  pl_val sum = x + y;
  if (!pl_is_nat63(sum))
    goto x_tail;
  NUMERIC_TAIL_RETURN(sum);
}
x_tail_sub: {
  NUMERIC_ARGS(x_tail, 4);
  NUMERIC_TAIL_RETURN(x > y ? x - y : 0);
}
x_tail_cmp: {
  NUMERIC_ARGS(x_tail, 4);
  NUMERIC_TAIL_RETURN(x < y ? 0 : (x == y ? 1 : 2));
}
#undef NUMERIC_TAIL_RETURN
#undef NUMERIC_RETURN
#undef NUMERIC_ARGS

x_call_known: {
  /* [argc, op, dead]: direct eager call of an ingest-resolved primop —
   * the args are already on the stack, so enter the strict-arg driver
   * without materializing (and immediately forcing) a thunk cell.
   * op_body's vsp = argbase - 1 drops the inserted op-index slot, and
   * ret_exec delivers the result exactly where MK_THK's cell sat.
   * (Skipping the slot for bodies that never read it measured within
   * noise on the plangrm bench, 2026-09-15: not worth the extra path.) */
  bool args_ready = fr->code->ops[fr->k - 1] == OP_CALL_READY;
  uint32_t nargs = (uint32_t)NEXT();
  uint32_t idx = (uint32_t)NEXT();
  (void)NEXT();
  assert(idx < pl_nops);
  if (nargs == 0 || nargs > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  if (pl_ops[idx].opset >= 82 && !t->rplan_f)
    pl_raise_msg(t, "Not in RPLAN Mode"); /* the F_OPENT gate */
  size_t abase = t->vsp - nargs;
  pl_vpush(t, 0); /* may realloc the vstack */
  pl_cache_stat_vstack_move(t, PL_CACHE_MOVE_CALL_KNOWN,
                            (size_t)nargs * sizeof(pl_val), 1);
  memmove(&t->vstack[abase + 1], &t->vstack[abase],
          (size_t)nargs * sizeof(pl_val));
  t->vstack[abase] = idx; /* the name slot op_body drops */
  op_idx = idx;
  op_base = abase + 1;
  op_argc = nargs;
  if (args_ready) {
    unsigned steps = (unsigned)__builtin_popcount(pl_ops[idx].strict_mask);
    if (t->fuel > steps) {
      t->fuel -= steps;
      goto op_args_ready;
    }
  }
  goto op_args;
}

x_call_fast: {
  /* [argc, hint]: [head, args…] on the stack; a verified law (or
   * pinned law) at exact arity enters judge in place — no thunk, no
   * update.  The hint operand is the caller-computed strict mask
   * consumed at the F_EXEC push.  Every call takes a fuel step
   * (non-tail self-recursion is otherwise unpreemptable); a yield
   * rewinds to re-execute the call with fresh fuel.  Anything the
   * verification rejects takes the generic slow-apply path. */
  size_t callf_pc = fr->k - 1;
  uint32_t nargs = (uint32_t)NEXT();
  (void)NEXT(); /* the caller's strictness hint: judge checks the args itself */
  if (nargs + 1 > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  size_t hb = t->vsp - nargs - 1;
  pl_val head = t->vstack[hb];
  pl_cell* lp = NULL;
  if (pl_tag(head) == PL_TAG_LAW)
    lp = pl_ptr(head);
  else if (pl_tag(head) == PL_TAG_PIN &&
           pl_tag(pl_pin_body(pl_ptr(head))) == PL_TAG_LAW)
    lp = pl_ptr(pl_pin_body(pl_ptr(head)));
  if (lp != NULL && pl_law_arity(lp) == nargs) {
    if (ax_unlikely(--t->fuel == 0) && pl_yield_now(t)) {
      fr->k = (uint32_t)callf_pc;
      t->resume_kind = PL_RES_RUN;
      pl_profile_pause_all(t);
      return PL_RUN_YIELDED;
    }
    hbase = hb;
    argc = nargs;
    goto judge;
  }
  /* mis-emitted or exotic head: generic apply, hint dropped */
  t->vstack[hb] = 0; /* head slot for ret_applyn */
  fr = pl_fpush(t);
  fr->kind = PL_F_APPLYN;
  fr->argbase = (uint32_t)(hb + 1);
  fr->argc = nargs;
  v = head;
  goto eval;
}

x_call_slow: {
  /* [argc]: [head, args…] on the stack; park the pending args under
   * one F_APPLYN frame and force the head — thke_slow without the
   * cell.  The eval safepoint owns any yield from here. */
  uint32_t nargs = (uint32_t)NEXT();
  if (nargs + 1 > t->vsp - fr->argbase)
    pl_raise_msg(t, "bytecode stack underflow");
  size_t hb = t->vsp - nargs - 1;
  pl_val head = t->vstack[hb];
  t->vstack[hb] = 0; /* head slot for ret_applyn */
  fr = pl_fpush(t);
  fr->kind = PL_F_APPLYN;
  fr->argbase = (uint32_t)(hb + 1);
  fr->argc = nargs;
  v = head;
  goto eval;
}
}
#undef DISPATCH
#undef NEXT

  /*
   * Decompose a law-body expression under env.  Mirrors KAL, except a
   * top-level application (0 f x) is evaluated in place (function side
   * pushed through an F_APPLY frame) rather than re-deferred.
   */
eval_expr:
  if (ax_unlikely(!pl_is_whnf(expr))) {
    /* dynamically-built body: force the expr itself first */
    fr = pl_fpush(t);
    fr->kind = PL_F_KAL;
    fr->a = env;
    v = expr;
    goto eval;
  }
  if (pl_is_nat63(expr)) {
    uint32_t n = pl_env_n(pl_ptr(env)) - 1;
    if (expr <= n) {
      v = pl_env_slots(pl_ptr(env))[expr];
      goto eval;
    }
    v = expr;
    goto ret; /* literal nat */
  }
  {
    pl_cell* p = pl_as(PL_TAG_APP, expr);
    if (p != NULL && pl_app_head(p) == 0) {
      uint32_t na = pl_app_n(p);
      if (na == 1) {
        v = pl_app_args(p)[0];
        goto eval; /* literal escape (0 x) */
      }
      if (na == 2) {
        /*
         * (0 f x): interpret both subexpressions, then evaluate the
         * function side with the lazy operand parked in an F_APPLY
         * frame.  The reference kal pattern-matches (unapps) each
         * subexpression, which forces it to WHNF first; the fast path
         * below covers the common already-WHNF case, the F_KAPP frame
         * the dynamically-built ones.
         *
         */
        if (pl_is_whnf(pl_app_args(p)[0]) && pl_is_whnf(pl_app_args(p)[1])) {
          pl_vpush(t, env);
          pl_vpush(t, expr);
          pl_gc_reserve(t, 2 * PL_THUNK_CELLS);
          expr = t->vstack[t->vsp - 1];
          env = t->vstack[t->vsp - 2];
          PL_GC_FORBID(t);
          pl_cell* ep = pl_ptr(expr);
          pl_val xv = pl_kal1(t, env, pl_app_args(ep)[1]);
          pl_val fv = pl_kal1(t, env, pl_app_args(ep)[0]);
          PL_GC_ALLOW(t);
          t->vsp -= 2;
          fr = pl_fpush(t);
          fr->kind = PL_F_APPLY;
          fr->b = xv;
          v = fv;
          goto eval;
        }
        fr = pl_fpush(t);
        fr->kind = PL_F_KAPP;
        fr->a = env;
        fr->b = expr;
        fr->k = 0;
        fr->argbase = (uint32_t)t->vsp;
        pl_vpush(t, 0); /* slot for the interpreted operand */
        v = pl_app_args(p)[1];
        goto eval;
      }
    }
  }
  v = expr; /* literal */
  goto ret;

ret:
  if (t->fsp == base) {
    t->result = v;
    return PL_RUN_DONE;
  }
  fr = &t->fstack[t->fsp - 1];
  if (ax_unlikely(fr->kind >= PL_F_KIND_COUNT || ret_tbl[fr->kind] == NULL))
    ax_abort("RETURN: bad frame kind %d", (int)fr->kind);
  goto* ret_tbl[fr->kind];

ret_update:
  pl_thunk_update(t, fr->a, v);
  t->fsp--;
  goto ret;

ret_upd:
  if (fr->argc == 0) {
    /* All consumers disappeared during collection; preserve the result. */
  } else if (fr->argc == 1) {
    pl_thke_update(t, fr->a, v);
  } else {
    ax_assume(fr->argc >= 2 && (size_t)fr->argbase + fr->argc - 1 == t->usp,
              "coalesced update stack is not a frame suffix");
    for (size_t i = fr->argc - 1; i > 0; i--)
      pl_thke_update(t, t->ustack[(size_t)fr->argbase + i - 1], v);
    pl_thke_update(t, fr->a, v);
    t->usp = fr->argbase;
  }
  t->fsp--;
  goto ret;

ret_kal:
  env = fr->a;
  expr = v;
  t->fsp--;
  goto eval_expr;

ret_kapp: {
  /* v is a WHNF subexpression of the (0 f x) in fr->b */
  if (fr->k == 0) {
    /* interpret the operand, then force the function subexpression */
    t->vstack[fr->argbase] = v; /* park: the reserve may move it */
    pl_gc_reserve(t, PL_THUNK_CELLS);
    PL_GC_FORBID(t);
    t->vstack[fr->argbase] = pl_kal1(t, fr->a, t->vstack[fr->argbase]);
    PL_GC_ALLOW(t);
    fr->k = 1;
    v = pl_app_args(pl_ptr(fr->b))[0];
    goto eval;
  }
  /* phase 1: park the function subexpr in its own slot (argbase
   * still holds the interpreted operand) */
  pl_vpush(t, v);
  pl_gc_reserve(t, PL_THUNK_CELLS);
  PL_GC_FORBID(t);
  pl_val fv = pl_kal1(t, fr->a, t->vstack[t->vsp - 1]);
  PL_GC_ALLOW(t);
  pl_val xv = t->vstack[fr->argbase];
  t->vsp = fr->argbase;
  fr->kind = PL_F_APPLY; /* reuse the frame slot */
  fr->a = 0;
  fr->b = xv;
  fr->k = 0;
  v = fv;
  goto eval;
}

ret_seq:
  v = fr->b;
  t->fsp--;
  goto eval;

ret_apply: {
  /* APPLY-STEP: v is the WHNF head, fr->b the pending argument */
  uint64_t need = pl_arity(v);
  if (need != 1) {
    uint32_t n = 0;
    {
      pl_cell* p = pl_as(PL_TAG_APP, v);
      if (p != NULL)
        n = pl_app_n(p);
    }
    pl_vpush(t, v);
    pl_gc_reserve(t, PL_APP_CELLS(n + 1));
    PL_GC_FORBID(t);
    pl_val f2 = pl_vpop(t);
    pl_val x2 = fr->b; /* re-read: collection rewrites frames in place */
    v = pl_mk_app_snoc(t, f2, x2);
    PL_GC_ALLOW(t);
    t->fsp--;
    goto ret;
  }
  /* saturated: ENTER */
  pl_val x = fr->b;
  t->fsp--;
  hbase = t->vsp;
  {
    pl_cell* p = pl_as(PL_TAG_APP, v);
    if (p != NULL) {
      pl_vpush(t, pl_app_head(p));
      uint32_t n = pl_app_n(p);
      for (uint32_t i = 0; i < n; i++)
        pl_vpush(t, pl_app_args(p)[i]);
    } else {
      pl_vpush(t, v);
    }
  }
  pl_vpush(t, x);
  goto fast_apply;

fast_apply:
  argc = (uint32_t)(t->vsp - hbase - 1);

  /* dispatch on the ultimate head: a LAW or a pinned law falls
   * through to judge, a pinned nat enters the op table */
  pl_val head = t->vstack[hbase];
  if (pl_is_nat63(head))
    ax_abort("ENTER: direct nat head");
  if (pl_tag(head) != PL_TAG_LAW) {
    if (ax_unlikely(pl_tag(head) != PL_TAG_PIN))
      ax_abort("ENTER: bad head tag 0x%llx", (unsigned long long)pl_tag(head));
    pl_val body = pl_pin_body(pl_ptr(head));
    if (pl_is_nat(body)) {
      /* primop: o applied to one argument whose spine is the op row */
      ax_assume(argc == 1, "pinned-nat arity must be 1");
      uint64_t o = pl_nat_u64_clamp(body);
      pl_val arg = t->vstack[hbase + 1];
      t->vsp = hbase;
      fr = pl_fpush(t);
      fr->kind = PL_F_OPENT;
      fr->opset = o;
      v = arg;
      goto eval;
    }
    if (pl_is_nat63(body) || pl_tag(body) != PL_TAG_LAW)
      pl_raise_msg(t, "tried to run a pinned app or pinned pin");
    /* pinned law: fall through to judge */
  }

judge: {
  pl_cell* lp = pl_lawp(t->vstack[hbase]);
  ax_assume(pl_law_arity(lp) == argc, "JUDGE: arity mismatch");
  bool profile_frame = pl_profile_law_push(t, t->vstack[hbase]);
  if (pl_hook != NULL) {
    pl_val out;
    t->centry_depth++; /* jets are C-entry regions */
    bool handled = pl_hook(t, hbase, argc, &out);
    t->centry_depth--;
    if (handled) {
      if (profile_frame) {
        pl_profile_frame_end(&t->fstack[t->fsp - 1]);
        t->fsp--;
      }
      t->vsp = hbase;
      v = out;
      goto eval;
    }
    /* An enter hook is a C-entry region and may allocate or collect.  The
     * head itself is rooted at hbase, but an unresolved PIN's LAW body moves
     * with its heap, so never retain the raw body pointer across the hook. */
    lp = pl_lawp(t->vstack[hbase]);
  }
  /*
   * JUDGE: the recursive-let prelude.  Scan the body for the (1 v k)
   * chain, then build the env knot in one no-collect window.
   * Layout on the value stack: [head, args… | cursor, bind-exprs…].
   */
  {
    /* Chain-free compiled entry: when the code never reads chain-bind
     * slots (max_var <= arity, no INTERP), skip the body scan and the
     * env/chain build entirely — the [head, args…] group stays on the
     * value stack and the frame runs stack-resident (PL_F_EXECV). */
    pl_code* scode = pl_law_code(t->vstack[hbase]);
    if (scode != NULL && scode->max_var <= argc) {
      fr = pl_fpush(t);
      fr->kind = PL_F_EXECV;
      fr->a = 0;
      fr->b = (pl_val)hbase;
      fr->argc = (uint32_t)(1 + argc);
      fr->code = scode;
      fr->k = pl_strict_entry(t, scode, hbase + 1, argc);
      fr->argbase = (uint32_t)t->vsp;
      goto exec;
    }
  }
  pl_vpush(t, pl_law_body(lp)); /* the chain cursor slot */
  jbase = hbase;
  jargc = argc;
  goto judge_scan;
}
}

ret_opent: {
  /* v is the WHNF op argument; unapp it to form [name, args…] */
  uint64_t opset = fr->opset;
  t->fsp--;
  size_t listbase = t->vsp;
  {
    pl_cell* p = pl_as(PL_TAG_APP, v);
    if (p != NULL) {
      pl_vpush(t, pl_app_head(p));
      uint32_t n = pl_app_n(p);
      for (uint32_t i = 0; i < n; i++)
        pl_vpush(t, pl_app_args(p)[i]);
    } else {
      pl_vpush(t, v);
    }
  }
  argc = (uint32_t)(t->vsp - listbase - 1);
  pl_val name = t->vstack[listbase];
  if (opset >= 82 && !t->rplan_f)
    pl_raise_msg(t, "Not in RPLAN Mode");
  int idx = pl_op_lookup(opset, name, argc);
  if (idx < 0)
    pl_raise_msgf(t, "no primop %llu (argc %u)", (unsigned long long)opset,
                  argc);
  op_idx = (uint32_t)idx;
  op_base = listbase + 1;
  op_argc = argc;
  goto op_args;
}

ret_oparg: {
  /* a forced strict arg comes back: park it, move to the next bit */
  t->vstack[fr->argbase + fr->k] = v;
  fr->k++;
  goto oparg_next;
}

ret_opdeep: {
  t->vstack[fr->argbase + fr->k] = v; /* deeply normalized arg k */
  fr->k++;
  goto opdeep_next;
}

ret_nf: {
  if (pl_is_normal(v)) {
    t->fsp--;
    goto ret;
  }
  fr->kind = PL_F_NFOBJ;
  fr->a = v;
  fr->k = 0;
  pl_push_nf(t);
  v = pl_nf_field(v, 0);
  goto eval;
}

ret_nfobj: {
  pl_nf_writeback(fr->a, fr->k, v);
  fr->k++;
  if (fr->k < pl_nf_nfields(fr->a)) {
    pl_push_nf(t);
    v = pl_nf_field(fr->a, fr->k);
    goto eval;
  }
  pl_cell* p = pl_ptr(fr->a);
  p[0] = pl_hdr_make(pl_hdr_kind(p[0]), pl_hdr_flags(p[0]) | PL_F_NORMAL,
                     pl_hdr_meta(p[0]), pl_hdr_cells(p[0]));
  v = fr->a;
  t->fsp--;
  goto ret;
}

ret_exec:
  pl_vpush(t, v); /* deliver to operand stack */
  goto exec;

ret_pure:
  if (getenv("PLAN_PURE_STATS") != NULL)
    fprintf(stderr, "[pure] return depth=%u remaining=%llu\n",
            t->pure_depth, (unsigned long long)t->pure_remaining);
  t->pure_remaining += fr->argc;
  t->pure_depth = fr->k;
  goto ret_try;

ret_try: {
  /* force (f x) succeeded under the barrier: the reference planTry's
   * Right, wrapped as (0 v).  The Left path lives in pl_run_caught. */
  t->fsp--;
  pl_vpush(t, v);
  pl_gc_reserve(t, PL_APP_CELLS(1));
  PL_GC_FORBID(t);
  v = pl_mk_app_from(t, 0, 1, &t->vstack[t->vsp - 1]);
  PL_GC_ALLOW(t);
  t->vsp--;
  goto ret;
}

ret_judge: {
  /* v is the forced chain node: write it back and resume the scan */
  jbase = fr->argbase;
  jargc = fr->argc;
  t->fsp--;
  t->vstack[jbase + 1 + jargc] = v;
  goto judge_scan;
}

ret_nil:
  /* planNil of the conditionally-forced value (op 66 Nor) */
  v = v == 0 ? 1 : 0;
  t->fsp--;
  goto ret;

ret_prof:
  pl_profile_frame_end(fr);
  t->fsp--;
  goto ret;

ret_memo:
  /* (f x) completed beneath the op-66 Memo barrier: record only nat63
   * results computed without initiating any effect (the epoch
   * watermark still matches).  An unwound or abandoned F_MEMO simply
   * never records; delivery is unconditional. */
  if (pl_is_nat63(v) && fr->epoch == t->effect_epoch)
    pl_memo_record(pl_pin_hash(fr->a), pl_pin_hash(fr->b), v);
  t->fsp--;
  goto ret;

ret_applyn: {
  /* v is the WHNF head; the pending args sit at [pbase, pbase+m) with
   * the reserved head slot at pbase-1.  The head's arity decides the
   * whole application here, in one step. */
  size_t pbase = fr->argbase;
  uint32_t m = fr->argc;
  uint64_t a = pl_arity(v);
  if (a == 0 || a > m) {
    /* data head or under-applied: the result is ONE flat app */
    uint32_t k = 0;
    {
      pl_cell* p = pl_as(PL_TAG_APP, v);
      if (p != NULL)
        k = pl_app_n(p);
    }
    pl_vpush(t, v);
    pl_gc_reserve(t, PL_APP_CELLS(k + m));
    PL_GC_FORBID(t);
    pl_val f2 = pl_vpop(t);
    v = pl_mk_app_cat(t, f2, m, &t->vstack[pbase]);
    PL_GC_ALLOW(t);
    t->vsp = pbase - 1;
    t->fsp--;
    goto ret;
  }
  t->fsp--;
  if (a < m) {
    /* over-applied: the excess tail waits in F_APPLY frames, first
     * excess arg topmost (left-to-right application order) */
    for (uint32_t i = m; i > (uint32_t)a; i--) {
      fr = pl_fpush(t);
      fr->kind = PL_F_APPLY;
      fr->b = t->vstack[pbase + i - 1];
    }
    t->vsp = pbase + (uint32_t)a;
  }
  /* exact arity: enter without building any intermediate app */
  if (pl_tag(v) == PL_TAG_LAW || pl_tag(v) == PL_TAG_PIN) {
    t->vstack[pbase - 1] = v;
    hbase = pbase - 1;
    goto fast_apply;
  }
  {
    /* partial-application head: splice its spine below the pending
     * args (spines are flat, so its head is a LAW or PIN) */
    pl_cell* p = pl_as(PL_TAG_APP, v);
    if (p == NULL)
      ax_abort("APPLYN: bad head tag 0x%llx", (unsigned long long)pl_tag(v));
    uint32_t k = pl_app_n(p);
    for (uint32_t j = 0; j < k; j++)
      pl_vpush(t, 0); /* may realloc the vstack; never collects */
    pl_cache_stat_vstack_move(t, PL_CACHE_MOVE_APPLY_SPLICE,
                              (size_t)a * sizeof(pl_val), (ptrdiff_t)k);
    memmove(&t->vstack[pbase + k], &t->vstack[pbase],
            (size_t)a * sizeof(pl_val));
    t->vstack[pbase - 1] = pl_app_head(p);
    memcpy(&t->vstack[pbase], pl_app_args(p), (size_t)k * sizeof(pl_val));
    hbase = pbase - 1;
    goto fast_apply;
  }
}

/* Ready arguments need no continuation. Materialize one only when forcing,
 * deep normalization, or a fuel checkpoint needs resumable state. Arguments
 * remain rooted on vstack throughout; the locals never survive a suspension. */
op_args: {
  const pl_opdesc* d = &pl_ops[op_idx];
  for (uint32_t k = 0; k < op_argc; k++) {
    if (((d->strict_mask >> k) & 1u) == 0)
      continue;
    v = t->vstack[op_base + k];
    if (!pl_is_whnf(v) || ax_unlikely(t->fuel == 1)) {
      fr = pl_fpush(t);
      fr->kind = PL_F_OPARG;
      fr->op = op_idx;
      fr->argbase = (uint32_t)op_base;
      fr->argc = op_argc;
      fr->k = k;
      goto eval;
    }
    /* Account for the eval step we bypass, including for ready arguments.
     * At fuel 1 the framed path above lets eval own the exact yield point. */
    t->fuel--;
  }
  goto op_args_ready;
}

op_args_ready: {
  const pl_opdesc* d = &pl_ops[op_idx];
#ifndef NDEBUG
  for (uint32_t k = 0; k < op_argc; k++)
    if ((d->strict_mask >> k) & 1u)
      assert(pl_is_whnf(t->vstack[op_base + k]));
#endif
  if (d->deep_mask != 0) {
    fr = pl_fpush(t);
    fr->kind = PL_F_OPDEEP;
    fr->op = op_idx;
    fr->argbase = (uint32_t)op_base;
    fr->argc = op_argc;
    fr->k = 0;
    goto opdeep_next;
  }
  goto op_body_ready;
}

oparg_next:
  /* fr is the F_OPARG frame on top of the stack */
  fr = &t->fstack[t->fsp - 1];
  {
    const pl_opdesc* d = &pl_ops[fr->op];
    while (fr->k < fr->argc) {
      if (((d->strict_mask >> fr->k) & 1u) == 0) {
        fr->k++;
        continue;
      }
      v = t->vstack[fr->argbase + fr->k];
      if (t->fuel == 1 || !pl_is_whnf(v))
        goto eval;
      t->fuel--;
      fr->k++;
    }
    if (d->deep_mask != 0) {
      fr->kind = PL_F_OPDEEP;
      fr->k = 0;
      goto opdeep_next;
    }
  }
  goto op_body;

judge_scan:
  /*
   * The recursive-let scan, re-enterable: its complete state is the
   * value stack plus (jbase, jargc) — the chain cursor sits at
   * jbase + 1 + jargc and the collected bind exprs above it.  A
   * non-WHNF chain node (dynamically-built law body) is forced through
   * the machine under an F_JUDGE frame, so the thread can suspend or
   * block mid-scan and resume with identical state.
   */
  {
    size_t cursor = jbase + 1 + jargc;
    for (;;) {
      pl_val b = t->vstack[cursor];
      if (!pl_is_whnf(b)) {
        fr = pl_fpush(t);
        fr->kind = PL_F_JUDGE;
        fr->argbase = (uint32_t)jbase;
        fr->argc = jargc;
        v = b;
        goto eval;
      }
      pl_cell* bp = pl_as(PL_TAG_APP, b);
      if (bp != NULL && pl_app_head(bp) == 1 && pl_app_n(bp) == 2) {
        /* bp stays valid across the vpush: growing the value stack
         * reallocs the stack array, never the heap */
        pl_vpush(t, pl_app_args(bp)[0]);
        t->vstack[cursor] = pl_app_args(bp)[1];
      } else {
        break;
      }
    }
    uint32_t m = (uint32_t)(t->vsp - cursor - 1);
    if (m == 0) {
      /* no chain binds: a compiled body can run with its [head, args…]
       * group left in place on the vstack — no env allocation at all
       * unless the body reifies one (pl_exec_reify_env) */
      pl_code* scode = pl_law_code(t->vstack[jbase]);
      if (scode != NULL) {
        t->vsp = cursor; /* drop the body cursor */
        fr = pl_fpush(t);
        fr->kind = PL_F_EXECV;
        fr->a = 0;
        fr->b = (pl_val)jbase;
        fr->argc = (uint32_t)(1 + jargc);
        fr->code = scode;
        fr->k = pl_strict_entry(t, scode, jbase + 1, jargc);
        fr->argbase = (uint32_t)t->vsp;
        goto exec;
      }
    }
    /* Decide the entry while the arguments still sit on the value stack:
     * the check resolves indirections in place before the env copies them. */
    pl_code* code = pl_law_code(t->vstack[jbase]);
    uint32_t fast_k =
        code != NULL ? pl_strict_entry(t, code, jbase + 1, jargc) : 0;
    uint32_t nslots = 1 + jargc + m;
    pl_gc_reserve(t, PL_ENV_CELLS(nslots) + (size_t)m * PL_THUNK_CELLS);
    PL_GC_FORBID(t);
    /* Every slot is written below before the no-collect window closes.  Avoid
     * zeroing what JUDGE immediately overwrites on every law entry. */
    pl_val envv = pl_mk_env_uninit(t, nslots);
    pl_val* slots = pl_env_slots(pl_ptr(envv));
    slots[0] = t->vstack[jbase];
    for (uint32_t i = 0; i < jargc; i++)
      slots[1 + i] = t->vstack[jbase + 1 + i];
    for (uint32_t j = 0; j < m; j++)
      slots[1 + jargc + j] = pl_mk_thunk(t, envv, t->vstack[cursor + 1 + j]);
    if (code != NULL) {
      t->vsp = jbase;
      fr = pl_fpush(t);
      fr->kind = PL_F_EXEC;
      fr->a = envv;
      fr->b = 0;
      fr->argc = 0; /* env mode: PUSH_VAR reads the env */
      fr->code = code;
      fr->k = fast_k;
      fr->argbase = (uint32_t)t->vsp;
      PL_GC_ALLOW(t);
      goto exec;
    }
    /* Tail skip: decompose the body in place under envv instead of
     * deferring it through a fresh unshared thunk (which would round-trip
     * defer_thunk's blackhole + F_UPDATE + dead update).  envv lives only
     * in `env` until eval_expr roots it (frame or vstack) before any
     * allocation. */
    expr = t->vstack[cursor];
    env = envv;
    PL_GC_ALLOW(t);
    t->vsp = jbase;
    goto eval_expr;
  }

opdeep_next:
  /* fr is the F_OPDEEP frame on top of the stack.  Deep (nf) phase
   * over the deep_mask args: payload normalization runs through the
   * machine at depth 0, so effects inside it block correctly. */
  fr = &t->fstack[t->fsp - 1];
  {
    const pl_opdesc* d = &pl_ops[fr->op];
    while (fr->k < fr->argc && ((d->deep_mask >> fr->k) & 1u) == 0)
      fr->k++;
    if (fr->k < fr->argc) {
      /* read through the frame before push_nf may move the array */
      size_t slot = fr->argbase + fr->k;
      pl_push_nf(t);
      v = t->vstack[slot];
      goto eval;
    }
  }
  goto op_body;

op_body:
  fr = &t->fstack[t->fsp - 1];
  op_idx = fr->op;
  op_base = fr->argbase;
  t->fsp--; /* pop before the body so its frames take this slot */
op_body_ready: {
  const pl_opdesc* d = &pl_ops[op_idx];
  /* Compiler profiling is observational only. A pure worker makes these
   * instrumentation calls inert rather than granting profiling authority. */
  if (ax_unlikely(t->pure_depth != 0) && d->name_c != NULL &&
      (strcmp(d->name_c, "ZoneStart") == 0 || strcmp(d->name_c, "ZoneEnd") == 0)) {
    t->vsp = op_base - 1;
    v = 0;
    goto ret;
  }
  /* Trace cannot emit from Pure. Preserve its return value so the compiler's
   * Trace(message, Throw(cause)) still returns the actual caught diagnostic. */
  if (ax_unlikely(t->pure_depth != 0) && d->opset == 66 &&
      d->name == ax_s5('T', 'r', 'a', 'c', 'e')) {
    v = t->vstack[op_base + 1];
    t->vsp = op_base - 1;
    goto eval;
  }
  if (ax_unlikely(t->pure_depth != 0) &&
      (d->opset == 82 || d->coord || d->host_effect ||
       (d->opset == 66 && (d->name == ax_s4('S','a','v','e') ||
         d->name == ax_s7('I','n','s','t','a','l','l') ||
         d->name == ax_s7('U','p','g','r','a','d','e') || d->name == ax_s5('T','r','a','c','e'))) ||
       (d->name_c != NULL && (strcmp(d->name_c, "ZoneStart") == 0 ||
                              strcmp(d->name_c, "ZoneEnd") == 0))))
    pl_raise_msgf(t, "Pure: external effect denied (%u/%llu)",
      (unsigned)d->opset, (unsigned long long)d->name);
  /* Ice interns immutable content, as Equal/Pin hashing already can. It
   * cannot publish a world root; Save/Install remain denied above. */
  uint32_t opi = op_idx;
  size_t argbase = op_base;
  t->centry_depth++; /* op bodies are C-entry regions */
  if (ax_unlikely(d->opset >= 82))
    t->effect_epoch++; /* effect initiation: F_MEMO barriers above must
                        * not record (covers direct ops, the io hook,
                        * and coordination requests alike) */
  pl_val r;
  if (ax_unlikely(d->host_effect && t->rplan_effect_f != NULL))
    t->rplan_effect_f(t);
  /* direct op-82 effects route through the record/replay seam */
  if (!(d->opset == 82 && !d->coord && pl_io != NULL &&
        pl_io(t, opi, argbase, &r)))
    r = d->body(t, argbase);
  t->centry_depth--;
  t->vsp = argbase - 1; /* drop args and the name slot */
  if (ax_unlikely(d->coord)) {
    /*
     * Coordination effect: r is the validated request, not a
     * result.  Initiation is legal only at depth 0 — directly
     * under pl_thread_run — where the machine parks the request and
     * suspends at a RETURN point: the deposited response arrives as
     * the op's value.  At depth > 0 under an executor, blocking is
     * impossible (live native frames sit between the trampoline and
     * this step), so reaching here is a contract violation — only a
     * jet or a host re-entry could do it.  From a plain host entry
     * there is nobody to service the request, so it is a
     * (non-Try-catchable) runtime error.
     */
    if (t->centry_depth > 0) {
      ax_assume(!t->suspendable,
                "coordination effect initiated in a C-entry region");
      pl_raise_msg(t, "actor op with no executor");
    }
    t->blocked_on = r;
    pl_profile_pause_all(t);
    return PL_RUN_BLOCKED;
  }
  v = r;
  if (t->fuel > 1 && pl_is_whnf(v)) {
    t->fuel--;
    goto ret;
  }
  goto eval;
}
}

/* ── Exception delivery (frame-based Try) ──────────────────────────────── */

/*
 * Every machine entry runs under this wrapper, which owns PLAN
 * exception delivery.  A raise longjmps here; if an F_TRY barrier
 * exists within THIS entry's frame range (and the exception is a
 * catchable PLAN_EXN, not a runtime error), the stacks unwind to the
 * barrier and the machine resumes by RETURNing (1 exn) — the reference
 * planTry's Left.  Otherwise the entry unwinds and the exception
 * re-raises to the next-outer handler (an enclosing entry's wrapper, a
 * host pl_catch, or pl_thread_run's top-level trap).
 *
 * Because Try is a frame, everything beneath it runs in the same
 * trampoline invocation: fuel yields, blocking coordination effects,
 * and resumption all work under Try, and a suspended continuation
 * carries its barriers across quanta.
 */
static pl_run_status pl_run_caught(pl_thread* t, pl_val v0, size_t base,
                                   uint8_t entry0) {
  /* modified across setjmp/longjmp iterations */
  volatile pl_val v = v0;
  volatile uint8_t entry = entry0;
  for (;;) {
    pl_catch c;
    pl_catch_init(t, &c);
    if (setjmp(c.jb) == 0) {
      pl_run_status s = pl_run(t, v, base, entry);
      pl_catch_pop(t, &c);
      return s;
    }
    t->handler = c.prev;
    t->centry_depth = c.centry;
    if (t->exn_msg == NULL || t->pure_depth != 0) {
      /* Only Pure catches runtime failures. Try retains its existing contract. */
      size_t i = t->fsp;
      while (i > base) {
        uint8_t kind = t->fstack[i - 1].kind;
        if (kind == PL_F_PURE || (t->exn_msg == NULL && kind == PL_F_TRY)) break;
        i--;
      }
      if (i > base) {
        if (t->exn_msg != NULL) {
          const char* message = t->exn_msg;
          t->exn = pl_nat_from_bytes(t, (const uint8_t*)message, strlen(message));
          t->exn_msg = NULL;
        }
        /* unwind to the barrier and deliver (1 exn) */
        uint64_t profile_mark = t->fstack[i - 1].profile_mark;
        uint32_t argbase = t->fstack[i - 1].argbase;
        pl_profile_pause_all(t);
        pl_unwind_frames(t, i - 1);
        t->vsp = argbase;
        pl_profile_drop_since_paused(t, profile_mark);
        pl_profile_resume_all(t);
        pl_gc_reserve(t, PL_APP_CELLS(1));
        PL_GC_FORBID(t);
        v = pl_mk_app_from(t, 1, 1, &t->exn);
        PL_GC_ALLOW(t);
        t->exn = 0;
        entry = PL_RES_RETURN;
        continue;
      }
    }
    /* uncaught within this entry: unwind it and propagate */
    pl_profile_pause_all(t);
    t->vsp = c.vsp;
    /* c.fsp may include an initially-pushed delivery frame which has already
     * returned.  base is the entry boundary and the actual unwind target. */
    pl_unwind_frames(t, base);
    pl_profile_drop_since_paused(t, c.profile_mark);
    if (c.centry > 0)
      pl_profile_resume_all(t);
    if (t->exn_msg != NULL)
      pl_raise_msg(t, t->exn_msg);
    pl_raise(t, t->exn);
  }
}

/* ── Suspendable execution ─────────────────────────────────────────────── */

static void pl_thread_unwind_run(pl_thread* t) {
  pl_profile_pause_all(t);
  t->vsp = t->base_vsp;
  pl_unwind_frames(t, t->base_fsp);
  pl_profile_drop_since_paused(t, t->profile_run_mark);
}

void pl_thread_start(pl_thread* t, pl_val v) {
  ax_assume(!t->suspendable && t->centry_depth == 0,
            "pl_thread_start: thread is running");
  t->base_vsp = t->vsp;
  t->base_fsp = t->fsp;
  t->resume_kind = PL_RES_EVAL;
  t->resume_val = v;
  t->blocked_on = 0;
  /* The old result is no longer observable once the new run is armed. */
  t->result = 0;
  t->pending_yield = false;
  t->profile_run_mark = t->profile_next_generation;
  t->status = PL_RUN_YIELDED;
}

void pl_thread_start_nf(pl_thread* t, pl_val v) {
  pl_thread_start(t, v);
  pl_frame* fr = pl_fpush(t); /* above base_fsp: pops exactly at DONE */
  fr->kind = PL_F_NF;
}

void pl_thread_start_call_nf(pl_thread* t, pl_val f, pl_val x) {
  pl_thread_start_nf(t, f);
  pl_frame* fr = pl_fpush(t); /* applied first, then the NF descent */
  fr->kind = PL_F_APPLY;
  fr->b = x;
}

void pl_thread_abandon(pl_thread* t) {
  ax_assume(!t->suspendable && t->centry_depth == 0,
            "pl_thread_abandon: thread is running");
  ax_assume(t->status == PL_RUN_BLOCKED,
            "pl_thread_abandon: thread is not blocked");
  pl_thread_unwind_run(t);
}

void pl_thread_deposit(pl_thread* t, pl_val response) {
  ax_assume(t->status == PL_RUN_BLOCKED,
            "pl_thread_deposit: thread is not blocked");
  /* the machine resumes by RETURNing the response to the pending frame,
   * which expects a WHNF (executors build rows/nats, never thunks) */
  ax_assume(pl_is_whnf(response), "pl_thread_deposit: response must be WHNF");
  t->resume_kind = PL_RES_RETURN;
  t->resume_val = response;
  t->blocked_on = 0;
  t->status = PL_RUN_YIELDED;
}

pl_val pl_thread_result(pl_thread* t) {
  ax_assume(t->status == PL_RUN_DONE, "pl_thread_result: thread not done");
  return t->result;
}

pl_val pl_thread_request(pl_thread* t) {
  ax_assume(t->status == PL_RUN_BLOCKED,
            "pl_thread_request: thread is not blocked");
  return t->blocked_on;
}

pl_run_status pl_thread_run(pl_thread* t, uint64_t fuel) {
  ax_assume(t->centry_depth == 0 && !t->suspendable,
            "pl_thread_run: re-entered from evaluator code");
  ax_assume(t->status == PL_RUN_YIELDED,
            "pl_thread_run: thread is not runnable (status %d) — "
            "start it or deposit a response first",
            (int)t->status);
  /* the per-step check pre-decrements, so fuel 1 would yield before the
   * first step and the thread could never progress */
  ax_assume(fuel >= 2, "pl_thread_run: fuel quantum must be >= 2");
  t->fuel = fuel;
  t->pending_yield = false;
  t->suspendable = true;
  uint64_t previous_profile_lane = pl_profile_active_lane;
  pl_profile_active_lane = t->profile_lane;

  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) != 0) {
    /* uncaught at thread top level: unwind to the entry watermarks;
     * t->exn / t->exn_msg carry the payload */
    t->handler = c.prev;
    pl_thread_unwind_run(t);
    t->centry_depth = 0;
    t->suspendable = false;
    t->fuel = UINT64_MAX;
    t->status = PL_RUN_EXN;
    pl_profile_active_lane = previous_profile_lane;
    return PL_RUN_EXN;
  }

  pl_profile_resume_all(t);
  pl_run_status s;
  switch (t->resume_kind) {
  case PL_RES_EVAL:
    s = pl_run_caught(t, t->resume_val, t->base_fsp, PL_RES_EVAL);
    break;
  case PL_RES_RETURN:
    s = pl_run_caught(t, t->resume_val, t->base_fsp, PL_RES_RETURN);
    break;
  case PL_RES_RUN:
    s = pl_run_caught(t, 0, t->base_fsp, PL_RES_RUN);
    break;
  default:
    ax_abort("pl_thread_run: bad resume kind %d", (int)t->resume_kind);
  }
  pl_catch_pop(t, &c);
  pl_profile_pause_all(t);
  t->suspendable = false;
  t->fuel = UINT64_MAX;
  t->status = (uint8_t)s;
  pl_profile_active_lane = previous_profile_lane;
  return s;
}

/* ── Entry points (host / C-entry) ─────────────────────────────────────── */

/*
 * Re-entrant evaluator call from host or op code: a C-entry region.
 * Runs with fuel inert (or pinned to the grace path under an executor)
 * and can therefore never suspend.
 */
static pl_val pl_run_centry(pl_thread* t, pl_val v, size_t base) {
  bool outermost = t->centry_depth == 0 && !t->suspendable;
  if (outermost)
    pl_profile_resume_all(t);
  t->centry_depth++;
  pl_run_status s = pl_run_caught(t, v, base, PL_RES_EVAL);
  t->centry_depth--;
  if (outermost)
    pl_profile_pause_all(t);
  ax_assume(s == PL_RUN_DONE, "C-entry run cannot suspend");
  pl_val result = t->result;
  /* Nested entries return directly to C; their caller roots what it keeps.
   * Leaving the scratch result here retains otherwise dead graphs for the
   * lifetime of the enclosing run. Preserve the outermost host result. */
  if (!outermost)
    t->result = 0;
  return result;
}

#ifdef PL_YIELD_STRESS
/*
 * YIELD_STRESS: at true depth 0, drive every host-API evaluation
 * through pl_thread_run at one machine step per quantum, so
 * the entire existing suite exercises suspension at every safepoint.
 * Results, exceptions, and stack effects must be indistinguishable from
 * the direct path.
 */
static pl_val pl_stress_drive(pl_thread* t, pl_val v, size_t base) {
  /* save any armed-but-not-running suspension state; vals stay rooted */
  size_t save_bvsp = t->base_vsp, save_bfsp = t->base_fsp;
  uint8_t save_kind = t->resume_kind, save_status = t->status;
  uint64_t save_profile_mark = t->profile_run_mark;
  size_t mark = t->vsp;
  pl_vpush(t, t->resume_val);
  pl_vpush(t, t->blocked_on);
  pl_vpush(t, t->result);

  t->base_vsp = t->vsp;
  t->base_fsp = base;
  t->resume_kind = PL_RES_EVAL;
  t->resume_val = v;
  t->blocked_on = 0;
  t->pending_yield = false;
  t->profile_run_mark = t->profile_next_generation;
  t->status = PL_RUN_YIELDED;

  pl_run_status s;
  do
    s = pl_thread_run(t, 2);
  while (s == PL_RUN_YIELDED);

  pl_val r = (s == PL_RUN_DONE) ? t->result : 0;
  t->result = t->vstack[mark + 2];
  t->blocked_on = t->vstack[mark + 1];
  t->resume_val = t->vstack[mark];
  t->vsp = mark;
  t->base_vsp = save_bvsp;
  t->base_fsp = save_bfsp;
  t->resume_kind = save_kind;
  t->status = save_status;
  t->profile_run_mark = save_profile_mark;
  /* Match pl_run_centry at true depth 0: the outermost host entry leaves its
   * result rooted in t->result (only nested entries clear it). */
  if (s == PL_RUN_DONE)
    t->result = r;

  if (s == PL_RUN_EXN) {
    /* re-raise to the caller's handler, as the direct path would */
    if (t->exn_msg != NULL)
      pl_raise_msg(t, t->exn_msg);
    pl_raise(t, t->exn);
  }
  if (s == PL_RUN_BLOCKED) {
    /* a coordination op reached depth 0 under the stress executor; the
     * direct path raises at initiation (centry_depth > 0) — match it */
    pl_raise_msg(t, "actor op with no executor");
  }
  return r;
}
#endif

static pl_val pl_eval_public(pl_thread* t, pl_val v, size_t base) {
#ifdef PL_YIELD_STRESS
  if (!t->suspendable && t->centry_depth == 0)
    return pl_stress_drive(t, v, base);
#endif
  return pl_run_centry(t, v, base);
}

pl_val pl_whnf(pl_thread* t, pl_val v) {
  return pl_eval_public(t, v, t->fsp);
}

pl_val pl_apply(pl_thread* t, pl_val f, pl_val x) {
  size_t base = t->fsp;
  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_APPLY;
  fr->b = x;
  return pl_eval_public(t, f, base);
}

pl_val pl_nf(pl_thread* t, pl_val v) {
  size_t base = t->fsp;
  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_NF;
  return pl_eval_public(t, v, base);
}
