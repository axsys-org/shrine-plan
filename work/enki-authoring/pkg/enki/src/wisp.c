#include "enki/wisp.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axsys/allocator.h"
#include "axsys/ds.h"
#include "axsys/util.h"
#include "enki/actor.h"
#include "plan/build.h"
#include "plan/debug.h"
#include "plan/nat.h"
#include "plan/store.h"

#define MOTE_HJUXT   ax_s5('#', 'j', 'u', 'x', 't')
#define MOTE_HBIND   ax_s5('#', 'b', 'i', 'n', 'd')
#define MOTE_HMACRO  ax_s6('#', 'm', 'a', 'c', 'r', 'o')
#define MOTE_HLAW    ax_s4('#', 'l', 'a', 'w')
#define MOTE_HPIN    ax_s4('#', 'p', 'i', 'n')
#define MOTE_HAPP    ax_s4('#', 'a', 'p', 'p')
#define MOTE_HEXPORT ax_s7('#', 'e', 'x', 'p', 'o', 'r', 't')
#define MOTE_MACRO   ax_s5('m', 'a', 'c', 'r', 'o')
#define MOTE_VALUE   ax_s5('v', 'a', 'l', 'u', 'e')

/* ── Lifecycle ─────────────────────────────────────────────────────────── */

/*
 * Law-compilation locals.  Names and bind expressions are referenced as
 * indices into the rooted scratch stack rather than as raw values: the
 * table stays valid across collections that move the heap.
 */
typedef struct en_local {
  size_t nam_i; /* w->tmp_v index of the local's name nat */
  uint64_t idx_q;
  size_t exp_i; /* w->tmp_v index of the bind expression, or SIZE_MAX */
} en_local;

static pl_val en_local_nam(en_wisp* w, const en_local* l) {
  return w->tmp_v[l->nam_i];
}

static void en_wisp_roots(pl_root_visit visit, void* gc_ctx, void* src_ctx) {
  en_wisp* w = src_ctx;
  for (en_env_entry* e = w->env; e != NULL; e = e->next) {
    pl_cache_stat_env_roots(w->t, 2);
    visit(&e->key_v, gc_ctx);
    visit(&e->val_v, gc_ctx);
  }
  for (size_t i = 0; i < w->tmp_s; i++)
    visit(&w->tmp_v[i], gc_ctx);
}

en_wisp* en_wisp_new(pl_heap* heap) {
  const ax_allocator* a = ax_allocator_system();
  en_wisp* w = ax_calloc(a, en_wisp, 1);
  if (w == NULL)
    return NULL;
  w->loc_a = a;
  w->heap = heap;
  w->t = pl_thread_new(heap);
  w->tmp_cap = 4096;
  w->tmp_v = malloc(w->tmp_cap * sizeof(pl_val));
  ax_assertf(w->tmp_v != NULL, "oom");
  pl_gc_add_root_source(heap, en_wisp_roots, w);
  return w;
}

void en_wisp_free(en_wisp* w) {
  if (w == NULL)
    return;
  pl_gc_del_root_source(w->heap, en_wisp_roots, w);
  en_env_entry* e = w->env;
  while (e != NULL) {
    en_env_entry* next = e->next;
    ax_free(w->loc_a, e);
    e = next;
  }
  free(w->msg_c);
  free(w->tmp_v);
  pl_thread_free(w->t);
  ax_free(w->loc_a, w);
}

[[noreturn]] static void en_fail_fn(en_wisp* w, const char* msg, int line) {
  if (w->err_f) {
    free(w->msg_c);
    w->msg_c = malloc(strlen(msg) + 1);
    if (w->msg_c != NULL)
      strcpy(w->msg_c, msg);
    longjmp(w->errjmp, 1);
  }
  fprintf(stderr, "wisp.c:%i fail: %s\r\n", line, msg);
  abort();
}

#define en_fail(w, msg) en_fail_fn(w, msg, __LINE__)

[[noreturn]] void en_wisp_fail(en_wisp* w, const char* msg) {
  en_fail(w, msg);
}

/* ── Rooted scratch ────────────────────────────────────────────────────── */

size_t en_root_mark(en_wisp* w) {
  return w->tmp_s;
}

void en_root_pop(en_wisp* w, size_t mark) {
  w->tmp_s = mark;
}

void en_root_push(en_wisp* w, pl_val v) {
  if (w->tmp_s == w->tmp_cap) {
    w->tmp_cap *= 2;
    w->tmp_v = realloc(w->tmp_v, w->tmp_cap * sizeof(pl_val));
    ax_assertf(w->tmp_v != NULL, "oom");
  }
  w->tmp_v[w->tmp_s++] = v;
}

/* Guarantee room for n more pushes without a realloc. */
static void en_root_reserve(en_wisp* w, size_t n) {
  if (w->tmp_cap - w->tmp_s >= n)
    return;
  size_t cap = w->tmp_cap;
  while (cap - w->tmp_s < n)
    cap *= 2;
  w->tmp_v = realloc(w->tmp_v, cap * sizeof(pl_val));
  ax_assertf(w->tmp_v != NULL, "oom");
  w->tmp_cap = cap;
}

/* ── Guarded evaluation ────────────────────────────────────────────────── */

[[noreturn]] static void en_fail_with_val(en_wisp* w, const char* msg,
                                          pl_val val);

[[noreturn]] static void en_fail_exn(en_wisp* w) {
  if (w->t->exn_msg != NULL)
    en_fail(w, w->t->exn_msg);
  en_fail_with_val(w, "PLAN exception", w->t->exn);
}

/* Scheduler-driven evaluation (the reference withNewRts): arm the
 * adopted root thread and drive the executor, so top-level code can
 * initiate coordination effects (Spawn/Send/Recv/…) that the scheduler
 * services while spawned actors run alongside. */
static pl_val en_run_drive(en_wisp* w, pl_val v, bool nf) {
  if (nf)
    pl_thread_start_nf(w->t, v);
  else
    pl_thread_start(w->t, v);
  er_drive_status ds = w->exec != NULL ? er_mt_executor_drive(w->exec, w->self)
                                       : er_scheduler_drive(w->sched, w->self);
  switch (ds) {
  case ER_DRIVE_DONE:
    return pl_thread_result(w->t);
  case ER_DRIVE_EXN:
    en_fail_exn(w);
  case ER_DRIVE_DEADLOCK:
  default:
    en_fail(w, "deadlock: every actor is blocked on Recv");
  }
}

pl_val en_run_whnf(en_wisp* w, pl_val v) {
  if (w->sched != NULL)
    return en_run_drive(w, v, false);
  pl_catch c;
  pl_catch_init(w->t, &c);
  if (setjmp(c.jb) == 0) {
    pl_val r = pl_whnf(w->t, v);
    pl_catch_pop(w->t, &c);
    return r;
  }
  pl_catch_unwind(w->t, &c);
  en_fail_exn(w);
}

pl_val en_run_nf(en_wisp* w, pl_val v) {
  if (w->sched != NULL)
    return en_run_drive(w, v, true);
  pl_catch c;
  pl_catch_init(w->t, &c);
  if (setjmp(c.jb) == 0) {
    pl_val r = pl_nf(w->t, v);
    pl_catch_pop(w->t, &c);
    return r;
  }
  pl_catch_unwind(w->t, &c);
  en_fail_exn(w);
}

/* ── Construction helpers ──────────────────────────────────────────────── */

pl_val en_app_make(en_wisp* w, pl_val fn, size_t n, const pl_val* args) {
  ax_assertf(n >= 1, "en_app_make: empty app");
  size_t mark = en_root_mark(w);
  /* Callers routinely pass args aliased into the root buffer itself
   * (&w->tmp_v[mark]).  Grow it once up front and re-derive the alias, so
   * the pushes below can never move the memory args points into. */
  uintptr_t lo = (uintptr_t)w->tmp_v;
  uintptr_t hi = lo + w->tmp_cap * sizeof(pl_val);
  uintptr_t ap = (uintptr_t)args;
  size_t alias_off = ap >= lo && ap < hi ? (size_t)(ap - lo) : SIZE_MAX;
  en_root_reserve(w, n + 1);
  if (alias_off != SIZE_MAX)
    args = (const pl_val*)((uintptr_t)w->tmp_v + alias_off);
  en_root_push(w, fn);
  for (size_t i = 0; i < n; i++)
    en_root_push(w, args[i]);
  pl_gc_reserve(w->t, PL_APP_CELLS(n));
  PL_GC_FORBID(w->t);
  pl_val out =
      pl_mk_app_from(w->t, w->tmp_v[mark], (uint32_t)n, &w->tmp_v[mark + 1]);
  PL_GC_ALLOW(w->t);
  en_root_pop(w, mark);
  return out;
}

static pl_val en_app1(en_wisp* w, pl_val fn, pl_val a) {
  pl_val args[] = {a};
  return en_app_make(w, fn, 1, args);
}

static pl_val en_app2(en_wisp* w, pl_val fn, pl_val a, pl_val b) {
  pl_val args[] = {a, b};
  return en_app_make(w, fn, 2, args);
}

static pl_val en_app3(en_wisp* w, pl_val fn, pl_val a, pl_val b, pl_val c) {
  pl_val args[] = {a, b, c};
  return en_app_make(w, fn, 3, args);
}

static pl_val en_quote(en_wisp* w, pl_val v) {
  return en_app1(w, 1, v);
}

static pl_val en_law_quote(en_wisp* w, pl_val v) {
  return en_app1(w, 0, v);
}

pl_val en_bytes_nat(en_wisp* w, const char* b, size_t n) {
  return pl_nat_from_bytes(w->t, (const uint8_t*)b, n);
}

pl_val en_string_nat(en_wisp* w, const char* s) {
  return en_bytes_nat(w, s, strlen(s));
}

/*
 * Lazy application: build a thunk that, when forced, folds the
 * applications left to right.  Encoded as the law-body expression
 * (0 .. (0 (0 v0) (0 v1)) .. (0 vn)) over an empty env.
 */
static pl_val en_delay_apply(en_wisp* w, size_t mark, size_t n) {
  if (n == 0)
    return 0;
  if (n == 1)
    return w->tmp_v[mark];
  size_t cells = PL_ENV_CELLS(1) + n * PL_APP_CELLS(1) +
                 (n - 1) * PL_APP_CELLS(2) + PL_THUNK_CELLS;
  pl_gc_reserve(w->t, cells);
  PL_GC_FORBID(w->t);
  pl_val env = pl_mk_env(w->t, 1);
  pl_val lit0[1] = {w->tmp_v[mark]};
  pl_val expr = pl_mk_app_from(w->t, 0, 1, lit0);
  for (size_t i = 1; i < n; i++) {
    pl_val liti[1] = {w->tmp_v[mark + i]};
    pl_val lit = pl_mk_app_from(w->t, 0, 1, liti);
    pl_val pair[2] = {expr, lit};
    expr = pl_mk_app_from(w->t, 0, 2, pair);
  }
  pl_val out = pl_mk_thunk(w->t, env, expr);
  PL_GC_ALLOW(w->t);
  return out;
}

/* The setjmp-protected body lives in its own function so no locals or
 * parameters cross the setjmp (gcc -Wclobbered). */
static pl_val en_run_apply_body(en_wisp* w, size_t mark, size_t n, bool nf) {
  size_t ri = en_root_mark(w);
  en_root_push(w, w->tmp_v[mark]);
  for (size_t i = 1; i < n; i++)
    w->tmp_v[ri] = pl_apply(w->t, w->tmp_v[ri], w->tmp_v[mark + i]);
  pl_val r = w->tmp_v[ri];
  r = nf ? pl_nf(w->t, r) : pl_whnf(w->t, r);
  en_root_pop(w, ri);
  return r;
}

/* Evaluate the application of the rooted values tmp[mark..mark+n). */
static pl_val en_run_apply_mode(en_wisp* w, size_t mark, size_t n, bool nf) {
  if (n == 0)
    return 0;
  /* volatile copies: parameters must not live across setjmp
   * (gcc -Wclobbered) */
  en_wisp* volatile w_v = w;
  volatile size_t mark_v = mark;
  volatile size_t n_v = n;
  volatile bool nf_v = nf;
  pl_catch c;
  pl_catch_init(w->t, &c);
  if (setjmp(c.jb) == 0) {
    pl_val r = en_run_apply_body(w_v, mark_v, n_v, nf_v);
    pl_catch_pop(w_v->t, &c);
    return r;
  }
  pl_catch_unwind(w_v->t, &c);
  en_fail_exn(w_v);
}

static pl_val en_run_apply(en_wisp* w, size_t mark, size_t n) {
  return en_run_apply_mode(w, mark, n, false);
}

/* ── Printing ──────────────────────────────────────────────────────────── */

char* en_wisp_print(en_wisp* w, pl_val v, size_t* out_s) {
  return pl_show(w->loc_a, v, out_s);
}

[[noreturn]] static void en_fail_with_val(en_wisp* w, const char* msg,
                                          pl_val val) {
  char* val_c = en_wisp_print(w, val, NULL);
  size_t n = strlen(msg) + strlen(val_c) + 5;
  char* buf = malloc(n);
  if (buf != NULL)
    snprintf(buf, n, "%s: %s", msg, val_c);
  ax_free(w->loc_a, val_c);
  if (w->err_f) {
    free(w->msg_c);
    w->msg_c = buf; /* owned by the wisp, freed in en_wisp_free */
    longjmp(w->errjmp, 1);
  }
  fprintf(stderr, "wisp fail: %s\n", buf != NULL ? buf : msg);
  abort();
}

/* ── Parser ────────────────────────────────────────────────────────────── */

static bool en_is_nat(pl_val v) {
  return pl_is_nat(v);
}

static pl_cell* en_as_app(pl_val v) {
  return pl_as(PL_TAG_APP, v);
}

typedef enum char_class {
  CL_EOF = 0,
  CL_WS,
  CL_STR,
  CL_END,
  CL_PAR,
  CL_BRA,
  CL_CUR,
  CL_SYM,
} char_class;

static char_class en_class(char c) {
  switch (c) {
  case 0:
    return CL_EOF;
  case ' ':
  case '\n':
  case ';':
    return CL_WS;
  case '"':
    return CL_STR;
  case ')':
  case ']':
  case '}':
    return CL_END;
  case '(':
    return CL_PAR;
  case '[':
    return CL_BRA;
  case '{':
    return CL_CUR;
  default:
    return CL_SYM;
  }
}

static bool en_eat(char** str) {
  for (;;) {
    if (**str == ';') {
      while (**str != '\n' && **str != 0)
        (*str)++;
    }
    if (**str == ' ' || **str == '\n') {
      (*str)++;
      continue;
    }
    return **str == 0;
  }
}

static pl_val en_parse_str(en_wisp* w, char** str_c) {
  char* sin_c = *str_c + 1;
  char* cur_c = sin_c;
  while (en_class(*cur_c) != CL_STR && en_class(*cur_c) != CL_EOF)
    cur_c++;
  if (en_class(*cur_c) == CL_EOF)
    en_fail(w, "unterminated string");
  size_t n = (size_t)(cur_c - sin_c);
  *str_c = cur_c + 1;
  return en_quote(w, en_bytes_nat(w, sin_c, n));
}

static bool en_is_close(char c) {
  return c == ')' || c == ']' || c == '}';
}

static bool en_is_gap(char c) {
  return c == ' ' || c == '\n' || c == ';';
}

static void en_expect_open(en_wisp* w, char** cur_c, char open_c) {
  if (**cur_c != open_c)
    en_fail(w, "expected opening delimiter");
  (*cur_c)++;
}

static bool en_take_seq_close(char** cur_c) {
  if (en_is_close(**cur_c)) {
    (*cur_c)++;
    return true;
  }
  return false;
}

/* Parse forms until a closer; items land on the rooted scratch stack. */
static size_t en_parse_items(en_wisp* w, char** str_c) {
  char* cur_c = *str_c;
  size_t count = 0;
  bool first = true;
  for (;;) {
    if (*cur_c == 0)
      en_fail(w, "eof in list");
    if (en_take_seq_close(&cur_c))
      break;
    if (!first && !en_is_gap(*cur_c))
      en_fail(w, "bad list");
    if (!first) {
      if (en_eat(&cur_c))
        en_fail(w, "eof in list");
      if (en_take_seq_close(&cur_c))
        break;
    }
    en_root_push(w, en_wisp_parse(w, &cur_c));
    count++;
    first = false;
  }
  *str_c = cur_c;
  return count;
}

static pl_val en_parse_par(en_wisp* w, char** str_c) {
  size_t mark = en_root_mark(w);
  size_t n = en_parse_items(w, str_c);
  if (n == 0) {
    en_root_pop(w, mark);
    return 0;
  }
  pl_val out = en_app_make(w, 0, n, &w->tmp_v[mark]);
  en_root_pop(w, mark);
  return out;
}

static pl_val en_parse_seq(en_wisp* w, pl_val tag, char** str_c) {
  size_t mark = en_root_mark(w);
  en_root_push(w, tag);
  size_t n = en_parse_items(w, str_c);
  pl_val out = en_app_make(w, 0, n + 1, &w->tmp_v[mark]);
  en_root_pop(w, mark);
  return out;
}

static pl_val en_parse_num(en_wisp* w, const char* s, size_t n) {
  bool ok = false;
  pl_val out = pl_nat_from_decimal(w->t, s, n, &ok);
  if (!ok)
    en_fail(w, "invalid number");
  return out;
}

static pl_val en_parse_sym(en_wisp* w, char** str_c) {
  char* cur_c = *str_c;
  bool num_f = true;
  while (en_class(*cur_c) == CL_SYM) {
    num_f &= (*cur_c <= '9') && (*cur_c >= '0');
    cur_c++;
  }
  char* sin_c = *str_c;
  *str_c = cur_c;
  size_t n = (size_t)(cur_c - sin_c);
  if (num_f)
    return en_quote(w, en_parse_num(w, sin_c, n));
  return en_bytes_nat(w, sin_c, n);
}

static pl_val en_parse_atom(en_wisp* w, char** str_c) {
  size_t mark = en_root_mark(w);
  en_root_push(w, en_parse_sym(w, str_c));
  char* cur_c = *str_c;
  char_class next = en_class(*cur_c);
  bool has_jux = false;
  pl_val jux = 0;

  if (next == CL_PAR) {
    has_jux = true;
    en_expect_open(w, &cur_c, '(');
    jux = en_parse_par(w, &cur_c);
  } else if (next == CL_BRA) {
    has_jux = true;
    en_expect_open(w, &cur_c, '[');
    jux = en_parse_seq(w, ax_s5('#', 'b', 'r', 'a', 'k'), &cur_c);
  } else if (next == CL_CUR) {
    has_jux = true;
    en_expect_open(w, &cur_c, '{');
    jux = en_parse_seq(w, ax_s5('#', 'c', 'u', 'r', 'l'), &cur_c);
  } else if (next == CL_STR) {
    has_jux = true;
    jux = en_parse_str(w, &cur_c);
  }
  *str_c = cur_c;
  pl_val sym = w->tmp_v[mark];
  pl_val out = has_jux ? en_app3(w, 0, MOTE_HJUXT, sym, jux) : sym;
  en_root_pop(w, mark);
  return out;
}

pl_val en_wisp_parse(en_wisp* w, char** str_c) {
  char* cur_c = *str_c;
  if (en_eat(&cur_c))
    en_fail(w, "eof");
  pl_val ret;
  switch (en_class(*cur_c)) {
  case CL_STR:
    ret = en_parse_str(w, &cur_c);
    break;
  case CL_SYM:
    ret = en_parse_atom(w, &cur_c);
    break;
  case CL_PAR:
    en_expect_open(w, &cur_c, '(');
    ret = en_parse_par(w, &cur_c);
    break;
  case CL_BRA:
    en_expect_open(w, &cur_c, '[');
    ret = en_parse_seq(w, ax_s5('#', 'b', 'r', 'a', 'k'), &cur_c);
    break;
  case CL_CUR:
    en_expect_open(w, &cur_c, '{');
    ret = en_parse_seq(w, ax_s5('#', 'c', 'u', 'r', 'l'), &cur_c);
    break;
  case CL_END:
    en_fail(w, "unexpected closing delimiter");
  default:
    en_fail(w, "eof");
  }
  *str_c = cur_c;
  return ret;
}

/* ── Environment ───────────────────────────────────────────────────────── */

en_env_entry* en_wisp_getenv(en_wisp* w, pl_val key) {
  if (!en_is_nat(key)) {
    pl_cache_stat_env_lookup(w->t, 0, false);
    return NULL;
  }
#ifdef PL_CACHE_STATS
  size_t probes = 0;
#endif
  for (en_env_entry* e = w->env; e != NULL; e = e->next) {
#ifdef PL_CACHE_STATS
    probes++;
#endif
    if (pl_nat_eq(e->key_v, key)) {
      pl_cache_stat_env_lookup(w->t, probes, true);
      return e;
    }
  }
  pl_cache_stat_env_lookup(w->t, probes, false);
  return NULL;
}

void en_wisp_putenv(en_wisp* w, pl_val key, bool mac_f, pl_val val) {
  if (!en_is_nat(key))
    en_fail_with_val(w, "bad env key", key);
  en_env_entry* e = en_wisp_getenv(w, key);
  if (e == NULL) {
    e = ax_calloc(w->loc_a, en_env_entry, 1);
    if (e == NULL)
      en_fail(w, "oom");
    e->key_v = key;
    e->next = w->env;
    w->env = e;
  }
  e->mac_f = (int)mac_f;
  e->val_v = val;
}

/*
 * Render the environment as the balanced-ish BST value handed to user
 * macros: node = (key macro|value val left right), empty = 0.
 */
typedef struct en_env_tmp {
  en_env_entry* ent;
  struct en_env_tmp* left;
  struct en_env_tmp* right;
} en_env_tmp;

static en_env_tmp* en_env_tmp_put(en_wisp* w, en_env_tmp* root,
                                  en_env_entry* ent) {
  if (root == NULL) {
    en_env_tmp* node = ax_calloc(w->loc_a, en_env_tmp, 1);
    if (node == NULL)
      en_fail(w, "oom");
    node->ent = ent;
    return node;
  }
  int cmp = pl_nat_cmp(ent->key_v, root->ent->key_v);
  if (cmp < 0)
    root->left = en_env_tmp_put(w, root->left, ent);
  else if (cmp > 0)
    root->right = en_env_tmp_put(w, root->right, ent);
  else
    root->ent = ent;
  return root;
}

static pl_val en_env_tmp_value(en_wisp* w, en_env_tmp* root) {
  if (root == NULL)
    return 0;
  size_t mark = en_root_mark(w);
  en_root_push(w, root->ent->mac_f ? MOTE_MACRO : MOTE_VALUE);
  en_root_push(w, root->ent->val_v);
  en_root_push(w, en_env_tmp_value(w, root->left));
  en_root_push(w, en_env_tmp_value(w, root->right));
  pl_val out = en_app_make(w, root->ent->key_v, 4, &w->tmp_v[mark]);
  en_root_pop(w, mark);
  return out;
}

static void en_env_tmp_free(en_wisp* w, en_env_tmp* root) {
  if (root == NULL)
    return;
  en_env_tmp_free(w, root->left);
  en_env_tmp_free(w, root->right);
  ax_free(w->loc_a, root);
}

static pl_val en_env_value(en_wisp* w) {
  en_env_entry** ents = NULL;
  for (en_env_entry* e = w->env; e != NULL; e = e->next)
    ax_arrpush(ents, e);
  en_env_tmp* root = NULL;
  for (size_t i = (size_t)ax_arrlen(ents); i > 0; i--)
    root = en_env_tmp_put(w, root, ents[i - 1]);
  ax_arrfree(ents);
  pl_val out = en_env_tmp_value(w, root);
  en_env_tmp_free(w, root);
  return out;
}

/* ── Macro expansion / law compilation ─────────────────────────────────── */

static bool en_is_juxt(pl_val v) {
  return v == MOTE_HJUXT;
}

static bool en_quote_payload(pl_val v, pl_val* out) {
  pl_cell* app = en_as_app(v);
  if (app != NULL && pl_app_head(app) == 1 && pl_app_n(app) == 1) {
    *out = pl_app_args(app)[0];
    return true;
  }
  return false;
}

static pl_val en_macroexpand_inn(en_wisp* w, size_t loc_s, en_local* loc,
                                 pl_val val);
static pl_val en_compile_expr(en_wisp* w, size_t loc_s, en_local* loc,
                              pl_val val);

static bool en_find_local(en_wisp* w, size_t loc_s, en_local* loc, pl_val nam,
                          uint64_t* idx) {
  for (size_t i = 0; i < loc_s; i++) {
    if (pl_nat_eq(en_local_nam(w, &loc[i]), nam)) {
      *idx = loc[i].idx_q;
      return true;
    }
  }
  return false;
}

static pl_val en_compile_expr(en_wisp* w, size_t loc_s, en_local* loc,
                              pl_val val) {
  if (val == 0)
    return en_law_quote(w, 0);
  if (en_is_nat(val)) {
    for (size_t i = 0; i < loc_s; i++) {
      if (pl_nat_eq(en_local_nam(w, &loc[i]), val))
        return loc[i].idx_q;
    }
    en_env_entry* ent = en_wisp_getenv(w, val);
    if (ent == NULL)
      en_fail_with_val(w, "unbound", val);
    return en_law_quote(w, ent->val_v);
  }

  pl_val payload = 0;
  if (en_quote_payload(val, &payload))
    return en_law_quote(w, payload);

  pl_cell* app = en_as_app(val);
  if (app == NULL || pl_app_head(app) != 0)
    return en_law_quote(w, val);

  size_t val_mark = en_root_mark(w);
  en_root_push(w, val);
  uint32_t n = pl_app_n(app);
  if (n == 0) {
    en_root_pop(w, val_mark);
    return en_law_quote(w, 0);
  }
  if (n == 3 && en_is_juxt(pl_app_args(app)[0]) &&
      pl_app_args(app)[1] == (pl_val)'#') {
    pl_val out = en_wisp_eval(w, pl_app_args(app)[2]);
    en_root_pop(w, val_mark);
    return out;
  }

  size_t mark = en_root_mark(w);
  app = en_as_app(w->tmp_v[val_mark]);
  en_root_push(w, en_compile_expr(w, loc_s, loc, pl_app_args(app)[0]));
  for (uint32_t i = 1; i < n; i++) {
    app = en_as_app(w->tmp_v[val_mark]);
    en_root_push(w, en_compile_expr(w, loc_s, loc, pl_app_args(app)[i]));
    w->tmp_v[mark] = en_app2(w, 0, w->tmp_v[mark], w->tmp_v[mark + 1]);
    en_root_pop(w, mark + 1);
  }
  pl_val out = w->tmp_v[mark];
  en_root_pop(w, val_mark);
  return out;
}

static void en_parse_bind(en_wisp* w, pl_val bin, pl_val* nam, pl_val* exp) {
  pl_cell* app = en_as_app(bin);
  if (app == NULL || pl_app_n(app) != 3 || !en_is_juxt(pl_app_args(app)[0]) ||
      !en_is_nat(pl_app_args(app)[1]))
    en_fail_with_val(w, "bad bind", bin);
  *nam = pl_app_args(app)[1];
  *exp = pl_app_args(app)[2];
}

static pl_val en_law_make(en_wisp* w, uint64_t arity, pl_val name,
                          pl_val body) {
  size_t mark = en_root_mark(w);
  en_root_push(w, name);
  en_root_push(w, body);
  pl_gc_reserve(w->t, PL_LAW_CELLS);
  PL_GC_FORBID(w->t);
  pl_val out = pl_mk_law(w->t, arity, w->tmp_v[mark], w->tmp_v[mark + 1]);
  PL_GC_ALLOW(w->t);
  en_root_pop(w, mark);
  return out;
}

/*
 * #law tag (name args…) binds… body — compile to a law whose body is the
 * (1 bind k) chain over compiled expressions.  Locals reference rooted
 * scratch slots by index, so the table survives collections.
 */
static pl_val en_law(en_wisp* w, pl_val tag, pl_val sig, pl_val bod,
                     size_t bin_s, const pl_val* bin_v) {
  size_t outer_mark = en_root_mark(w);
  en_root_push(w, sig);
  en_root_push(w, bod);
  for (size_t i = 0; i < bin_s; i++)
    en_root_push(w, bin_v[i]);
  size_t sig_i = outer_mark, bod_i = outer_mark + 1, bin_i = outer_mark + 2;

  size_t teg_i = en_root_mark(w);
  en_root_push(w, en_wisp_eval(w, tag));

  pl_cell* app = en_as_app(w->tmp_v[sig_i]);
  if (app == NULL || pl_app_head(app) != 0 || pl_app_n(app) < 2)
    en_fail_with_val(w, "bad law signature", w->tmp_v[sig_i]);
  if (!en_is_nat(pl_app_args(app)[0]))
    en_fail_with_val(w, "bad law name", pl_app_args(app)[0]);

  size_t arg_s = pl_app_n(app) - 1;
  if (arg_s > UINT32_MAX)
    en_fail_with_val(w, "law arity overflow", w->tmp_v[sig_i]);

  size_t loc_s = arg_s + bin_s + 1;
  en_local* loc = ax_calloc(w->loc_a, en_local, loc_s);
  if (loc == NULL)
    en_fail(w, "oom");

  /* park names and bind expressions in rooted slots */
  size_t nam_base = en_root_mark(w);
  for (size_t i = 0; i <= arg_s; i++) {
    app = en_as_app(w->tmp_v[sig_i]);
    pl_val a = pl_app_args(app)[i];
    if (i > 0 && !en_is_nat(a))
      en_fail_with_val(w, "bad law argument", a);
    en_root_push(w, a);
    loc[i].nam_i = nam_base + i;
    loc[i].idx_q = i;
    loc[i].exp_i = SIZE_MAX;
  }
  size_t exp_base = en_root_mark(w);
  for (size_t j = 0; j < bin_s; j++) {
    pl_val bnam, bexp;
    en_parse_bind(w, w->tmp_v[bin_i + j], &bnam, &bexp);
    en_root_push(w, bnam);
    en_root_push(w, bexp);
    loc[arg_s + 1 + j].nam_i = exp_base + 2 * j;
    loc[arg_s + 1 + j].idx_q = arg_s + 1 + j;
    loc[arg_s + 1 + j].exp_i = exp_base + 2 * j + 1;
  }

  /* macroexpand bind expressions and the body under the locals */
  size_t expexp_base = en_root_mark(w);
  for (size_t j = 0; j < bin_s; j++) {
    en_root_push(w, en_macroexpand_inn(w, loc_s, loc,
                                       w->tmp_v[loc[arg_s + 1 + j].exp_i]));
  }
  size_t bodexp_i = en_root_mark(w);
  en_root_push(w, en_macroexpand_inn(w, loc_s, loc, w->tmp_v[bod_i]));

  /* compile */
  size_t let_base = en_root_mark(w);
  for (size_t j = 0; j < bin_s; j++) {
    en_root_push(w, en_compile_expr(w, loc_s, loc, w->tmp_v[expexp_base + j]));
  }
  size_t body_i = en_root_mark(w);
  en_root_push(w, en_compile_expr(w, loc_s, loc, w->tmp_v[bodexp_i]));
  for (size_t j = bin_s; j > 0; j--) {
    w->tmp_v[body_i] =
        en_app2(w, 1, w->tmp_v[let_base + j - 1], w->tmp_v[body_i]);
  }
  ax_free(w->loc_a, loc);
  pl_val law = en_law_make(w, arg_s, w->tmp_v[teg_i], w->tmp_v[body_i]);
  en_root_pop(w, outer_mark);
  return en_quote(w, law);
}

static pl_val en_pin(en_wisp* w, pl_val val) {
  size_t mark = en_root_mark(w);
  en_root_push(w, en_wisp_eval(w, val));
  pl_catch c;
  pl_catch_init(w->t, &c);
  if (setjmp(c.jb) != 0) {
    pl_catch_unwind(w->t, &c);
    en_fail_exn(w);
  }
  w->tmp_v[mark] = pl_pin(w->t, w->tmp_v[mark]);
  pl_catch_pop(w->t, &c);
  /* A provisional PIN is an ordinary moving value.  Keep it in the Wisp
   * root set while en_quote reserves space for the wrapper application. */
  pl_val out = en_quote(w, w->tmp_v[mark]);
  en_root_pop(w, mark);
  return out;
}

static pl_val en_bind(en_wisp* w, pl_val nam, pl_val val, bool mac_f) {
  if (!en_is_nat(nam))
    en_fail_with_val(w, "bad env key", nam);
  size_t mark = en_root_mark(w);
  en_root_push(w, nam);
  pl_val vel = en_wisp_eval(w, val);
  en_wisp_putenv(w, w->tmp_v[mark], mac_f, vel);
  pl_val out = en_quote(w, w->tmp_v[mark]);
  en_root_pop(w, mark);
  return out;
}

static pl_val en_app_macro(en_wisp* w, size_t exp_s, const pl_val* exp_v) {
  if (exp_s == 0)
    return en_quote(w, 0);
  size_t mark = en_root_mark(w);
  for (size_t i = 0; i < exp_s; i++)
    en_root_push(w, exp_v[i]);
  size_t out_mark = en_root_mark(w);
  for (size_t i = 0; i < exp_s; i++)
    en_root_push(w, en_wisp_eval(w, w->tmp_v[mark + i]));
  pl_val res = en_run_apply(w, out_mark, exp_s);
  en_root_pop(w, mark);
  return en_quote(w, res);
}

static pl_val en_export(en_wisp* w, size_t sym_s, const pl_val* sym_v) {
  en_env_entry** keep = NULL;
  for (size_t i = 0; i < sym_s; i++) {
    if (!en_is_nat(sym_v[i]))
      en_fail_with_val(w, "bad export", sym_v[i]);
    en_env_entry* ent = en_wisp_getenv(w, sym_v[i]);
    if (ent == NULL)
      en_fail_with_val(w, "unbound export", sym_v[i]);
    ax_arrpush(keep, ent);
  }
  /* keep entries alive: they are spliced into a fresh list */
  en_env_entry* old = w->env;
  w->env = NULL;
  for (size_t i = 0; i < sym_s; i++)
    en_wisp_putenv(w, keep[i]->key_v, (bool)keep[i]->mac_f, keep[i]->val_v);
  ax_arrfree(keep);
  en_env_entry* e = old;
  while (e != NULL) {
    en_env_entry* next = e->next;
    ax_free(w->loc_a, e);
    e = next;
  }
  return 0;
}

static pl_val en_expand_user(en_wisp* w, pl_val mac, pl_val val) {
  size_t mark = en_root_mark(w);
  en_root_push(w, mac);
  en_root_push(w, val);
  en_root_push(w, 0); /* env slot */
  w->tmp_v[mark + 2] = en_env_value(w);
  /* order for apply: mac env val */
  pl_val tmp = w->tmp_v[mark + 1];
  w->tmp_v[mark + 1] = w->tmp_v[mark + 2];
  w->tmp_v[mark + 2] = tmp;
  pl_val out = en_run_apply_mode(w, mark, 3, true);
  en_root_pop(w, mark);
  return out;
}

static bool en_is_sys_macro(pl_val v) {
  return v == MOTE_HBIND || v == MOTE_HLAW || v == MOTE_HPIN ||
         v == MOTE_HMACRO || v == MOTE_HAPP || v == MOTE_HEXPORT;
}

static pl_val en_expand1(en_wisp* w, uint64_t mac, pl_val val) {
  pl_cell* app = en_as_app(val);
  if (app == NULL)
    en_fail(w, "expected row expanding macro");
  uint32_t n = pl_app_n(app);

  switch (mac) {
  case MOTE_HBIND:
    if (n != 3)
      en_fail_with_val(w, "invalid #bind", val);
    return en_bind(w, pl_app_args(app)[1], pl_app_args(app)[2], false);
  case MOTE_HMACRO:
    if (n != 3)
      en_fail_with_val(w, "invalid #macro", val);
    return en_bind(w, pl_app_args(app)[1], pl_app_args(app)[2], true);
  case MOTE_HPIN:
    if (n != 2)
      en_fail_with_val(w, "invalid #pin", val);
    return en_pin(w, pl_app_args(app)[1]);
  case MOTE_HLAW:
    if (n < 4)
      en_fail_with_val(w, "invalid #law", val);
    return en_law(w, pl_app_args(app)[1], pl_app_args(app)[2],
                  pl_app_args(app)[n - 1], n - 4, &pl_app_args(app)[3]);
  case MOTE_HAPP:
    if (n < 1)
      en_fail_with_val(w, "invalid #app", val);
    return en_app_macro(w, n - 1, &pl_app_args(app)[1]);
  case MOTE_HEXPORT:
    return en_export(w, n - 1, &pl_app_args(app)[1]);
  default:
    en_fail_with_val(w, "unknown macro", mac);
  }
}

static pl_val en_macroexpand_inn(en_wisp* w, size_t loc_s, en_local* loc,
                                 pl_val val) {
  if (en_is_nat(val))
    return val;
  pl_cell* app = en_as_app(val);
  if (app == NULL)
    return val;

  size_t val_mark = en_root_mark(w);
  en_root_push(w, val);

#define APP() en_as_app(w->tmp_v[val_mark])

  if (pl_app_head(app) != 0) {
    en_root_pop(w, val_mark);
    return val;
  }
  uint32_t n = pl_app_n(app);

  if (n == 3 && en_is_juxt(pl_app_args(app)[0]) &&
      pl_app_args(app)[1] == (pl_val)'#' && loc_s > 0) {
    pl_val inn = en_macroexpand_inn(w, loc_s, loc, pl_app_args(app)[2]);
    en_root_push(w, inn);
    app = APP();
    pl_val out =
        en_app3(w, 0, pl_app_args(app)[0], '#', w->tmp_v[en_root_mark(w) - 1]);
    en_root_pop(w, val_mark);
    return out;
  }

  if (n == 0) {
    pl_val out = w->tmp_v[val_mark];
    en_root_pop(w, val_mark);
    return out;
  }

  uint64_t local_idx = 0;
  pl_val head0 = pl_app_args(app)[0];
  bool head_is_local =
      en_is_nat(head0) && en_find_local(w, loc_s, loc, head0, &local_idx);
  if (!head_is_local && en_is_nat(head0)) {
    en_env_entry* ent = en_wisp_getenv(w, head0);
    if (ent != NULL) {
      if (ent->mac_f) {
        pl_val out = en_expand_user(w, ent->val_v, w->tmp_v[val_mark]);
        en_root_pop(w, val_mark);
        return en_macroexpand_inn(w, loc_s, loc, out);
      }
    } else if (pl_is_nat63(head0) && en_is_sys_macro(head0)) {
      pl_val out = en_expand1(w, head0, w->tmp_v[val_mark]);
      en_root_pop(w, val_mark);
      return en_macroexpand_inn(w, loc_s, loc, out);
    }
  }

  size_t mark = en_root_mark(w);
  for (uint32_t i = 0; i < n; i++) {
    app = APP();
    en_root_push(w, en_macroexpand_inn(w, loc_s, loc, pl_app_args(app)[i]));
  }
  pl_val out = en_app_make(w, 0, n, &w->tmp_v[mark]);
  en_root_pop(w, val_mark);
  return out;
#undef APP
}

/* ── Top-level evaluation ──────────────────────────────────────────────── */

static pl_val en_delay(en_wisp* w, pl_val val);

static pl_val en_delay(en_wisp* w, pl_val val) {
  if (val == 0)
    return 0;
  if (en_is_nat(val)) {
    en_env_entry* ent = en_wisp_getenv(w, val);
    if (ent == NULL)
      en_fail_with_val(w, "unbound thk", val);
    return ent->val_v;
  }
  pl_cell* app = en_as_app(val);
  if (app == NULL)
    return val;
  if (pl_app_head(app) == 1 && pl_app_n(app) == 1)
    return pl_app_args(app)[0];
  if (pl_app_head(app) != 0)
    en_fail_with_val(w, "thunk: expected list", val);

  size_t val_mark = en_root_mark(w);
  en_root_push(w, val);
  size_t mark = en_root_mark(w);
  uint32_t n = pl_app_n(app);
  for (uint32_t i = 0; i < n; i++) {
    app = en_as_app(w->tmp_v[val_mark]);
    en_root_push(w, en_delay(w, pl_app_args(app)[i]));
  }
  pl_val out = en_delay_apply(w, mark, n);
  en_root_pop(w, val_mark);
  return out;
}

pl_val en_wisp_thunk(en_wisp* w, pl_val val) {
  if (val == 0)
    return 0;
  if (en_is_nat(val)) {
    en_env_entry* ent = en_wisp_getenv(w, val);
    if (ent == NULL)
      en_fail_with_val(w, "unbound thk", val);
    return ent->val_v;
  }
  pl_cell* app = en_as_app(val);
  if (app == NULL)
    return val;
  if (pl_app_head(app) == 1 && pl_app_n(app) == 1)
    return pl_app_args(app)[0];
  if (pl_app_head(app) != 0)
    en_fail_with_val(w, "thunk: expected list", val);

  size_t val_mark = en_root_mark(w);
  en_root_push(w, val);
  size_t mark = en_root_mark(w);
  uint32_t n = pl_app_n(app);
  for (uint32_t i = 0; i < n; i++) {
    app = en_as_app(w->tmp_v[val_mark]);
    pl_val item = i == 0 ? en_wisp_thunk(w, pl_app_args(app)[i])
                         : en_delay(w, pl_app_args(app)[i]);
    en_root_push(w, item);
  }
  pl_val out = en_run_apply(w, mark, n);
  en_root_pop(w, val_mark);
  return out;
}

pl_val en_wisp_macroexpand(en_wisp* w, pl_val val) {
  return en_macroexpand_inn(w, 0, NULL, val);
}

pl_val en_wisp_eval(en_wisp* w, pl_val val) {
  pl_val exp = en_wisp_macroexpand(w, val);
  return en_wisp_thunk(w, exp);
}
