#include "plan/canon.h"

#include <gmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axsys/allocator.h"
#include "axsys/arena.h"
#include "axsys/assume.h"
#include "axsys/base58.h"
#include "axsys/sb.h"
#include "axsys/ds.h"
#include "plan/nat.h"
#include "plan/store.h"
#include "plan/xtract.h"

/*
 * Faithful port of the reference printer (Print.hs).  Printing is split
 * into passes over an intermediate Doc tree:
 *
 *   extract     decode the value; pins become refs, law vars raw indices
 *               (the reference nameSelf is fused in: var 0 of each law is
 *               already its tag-derived self name)
 *   nameGlobal  assign names to pin refs (tag hints, then base58 stubs)
 *   nameVars    fill remaining law variables with short local names
 *   render      flat-or-wide layout with greedy line packing
 *
 * Everything is allocated from one scratch arena per call; only the
 * final string is copied to the caller's allocator.
 */

/* ── Doc tree ──────────────────────────────────────────────────────────── */

typedef enum { CN_RPIN, CN_RVAR, CN_RSELF } cn_refkind;

typedef struct cn_ref {
  cn_refkind rk;
  pl_val pin;       /* CN_RPIN */
  const char* hint; /* CN_RPIN: tag-derived name, or NULL */
  uint64_t var;     /* CN_RVAR: raw de Bruijn-style index */
  const char* name; /* resolved name (nameGlobal / nameVars) */
} cn_ref;

typedef struct cn_doc cn_doc;
typedef struct cn_expr cn_expr;

typedef struct cn_law {
  cn_doc* tag;
  cn_ref* self;
  cn_ref** args;
  size_t nargs;
  cn_ref** lets; /* let binders */
  cn_expr** rhss;
  size_t nlets;
  cn_expr* body;
} cn_law;

typedef enum {
  CN_DNUM,
  CN_DSTR,
  CN_DREF,
  CN_DPIN,
  CN_DLIQUID,
  CN_DLAW,
  CN_DAPP
} cn_dkind;

struct cn_doc {
  cn_dkind k;
  pl_val nat;    /* DNUM / DSTR */
  cn_ref* ref;   /* DREF */
  cn_doc* inner; /* DPIN */
  cn_law* law;   /* DLAW */
  cn_doc* head;  /* DAPP */
  cn_doc** args;
  size_t nargs;
};

typedef enum { CN_EVAR, CN_ECONST, CN_EAPP, CN_EESC } cn_ekind;

struct cn_expr {
  cn_ekind k;
  cn_ref* ref; /* EVAR */
  cn_doc* doc; /* ECONST / EESC */
  cn_expr *f, *x;
};

typedef struct cn_global {
  pl_val pin;
  const char* hint; /* NULL for unnamed */
  const char* name; /* assigned */
  char b58[AX_BASE58_CAP(32)];
} cn_global;

typedef struct cn_pin_idx {
  pl_val key;
  size_t value; /* index into globals */
} cn_pin_idx;

typedef struct cn {
  ax_arena* ar;
  int maxw;
  /* globals, first occurrence in orderedGlobals traversal order */
  cn_global* globals; /* stb_ds array */
  cn_pin_idx* pinidx; /* stb_ds hashmap pin val -> index */
  const char** used;  /* stb_ds array: reserved/assigned names */
  char** temps;       /* system-allocated render strings */
  int nc;             /* nameVars fresh counter, threads whole doc */
} cn;

#define CN_ARENA_CAP ((size_t)1 << 31)

static void* cn_alloc(cn* c, size_t n) {
  void* p = ax_arena_alloc(c->ar, n);
  ax_assume(p != NULL, "canon: arena exhausted");
  return p;
}

static size_t cn_arena_mark(cn* c) {
  return c->ar->off_o;
}

static void cn_arena_rewind(cn* c, size_t mark) {
  ax_assume(mark >= sizeof(ax_arena) && mark <= c->ar->off_o,
            "canon: bad arena mark");
  c->ar->off_o = mark;
}

static const char* cn_cstr(const char* where, const char* s) {
  ax_assume(s != NULL, "canon: null string from %s", where);
  return s;
}

static size_t cn_strlen(const char* where, const char* s) {
  ax_assume(s != NULL, "canon: null string length from %s", where);
  return strlen(s);
}

static void cn_sb_append_cstr(ax_sb* sb, const char* where, const char* s) {
  ax_assume(s != NULL, "canon: null string append from %s", where);
  ax_assume(ax_sb_append_cstr(sb, s), "canon: string builder failed at %s",
            where);
}

static void cn_sb_init(ax_sb* sb) {
  ax_sb_init(sb, ax_allocator_system());
}

static const char* cn_sb_build(cn* c, ax_sb* sb, const char* where) {
  char* s = ax_sb_build_with_allocator(sb, ax_allocator_system(), NULL);
  cn_cstr(where, s);
  ax_sb_free(sb);
  ax_arrpush(c->temps, s);
  return s;
}

static const char* cn_overwide(cn* c) {
  static char s[4096];
  if (s[0] == '\0') {
    s[0] = '(';
    memset(s + 1, 'x', sizeof(s) - 2);
    s[sizeof(s) - 1] = '\0';
  }
  ax_assume((size_t)c->maxw < sizeof(s) - 1, "canon: max width too large");
  return s;
}

static const char* cn_sb_build_flat(cn* c, ax_sb* sb, const char* where) {
  size_t len = 0;
  ax_assume(ax_sb_measure(sb, &len), "canon: string builder failed at %s",
            where);
  if (len > (size_t)c->maxw) {
    ax_sb_free(sb);
    return cn_overwide(c);
  }
  return cn_sb_build(c, sb, where);
}

static char* cn_strdup_n(cn* c, const char* s, size_t n) {
  char* d = cn_alloc(c, n + 1);
  memcpy(d, s, n);
  d[n] = '\0';
  return d;
}

static const char* cn_cat_v(cn* c, const char* const* parts) {
  size_t n = 0;
  for (size_t i = 0; parts[i] != NULL; i++)
    n += cn_strlen("CN_CAT", parts[i]);
  char* out = ax_calloc(ax_allocator_system(), char, n + 1);
  ax_assume(out != NULL, "canon: oom");
  ax_arrpush(c->temps, out);
  char* p = out;
  for (size_t i = 0; parts[i] != NULL; i++) {
    size_t l = cn_strlen("CN_CAT", parts[i]);
    memcpy(p, parts[i], l);
    p += l;
  }
  *p = '\0';
  return out;
}

#define CN_CAT(c, ...) cn_cat_v(c, (const char* const[]){__VA_ARGS__, NULL})

/* "\n" followed by col spaces */
static const char* cn_nl(cn* c, int col) {
  char* s = ax_calloc(ax_allocator_system(), char, (size_t)col + 2);
  ax_assume(s != NULL, "canon: oom");
  ax_arrpush(c->temps, s);
  s[0] = '\n';
  memset(s + 1, ' ', (size_t)col);
  s[col + 1] = '\0';
  return s;
}

/* ── Nat rendering helpers ─────────────────────────────────────────────── */

static void cn_gmp_free(void* ptr, size_t size_s) {
  if (ptr == NULL)
    return;
  void (*free_fn)(void*, size_t) = NULL;
  mp_get_memory_functions(NULL, NULL, &free_fn);
  free_fn(ptr, size_s);
}

static const char* cn_num_str(cn* c, pl_val v) {
  if (pl_is_nat63(v)) {
    char buf[24];
    int n = snprintf(buf, sizeof(buf), "%llu", (unsigned long long)v);
    return cn_strdup_n(c, buf, (size_t)n);
  }
  mpz_t z;
  mpz_init(z);
  size_t limbs = pl_nat_limb_len(v);
  mpz_import(z, limbs, -1, sizeof(uint64_t), 0, 0, pl_nat_limb_ptr(pl_ptr(v)));
  char* dec = mpz_get_str(NULL, 10, z);
  const char* out = cn_strdup_n(c, dec, strlen(dec));
  cn_gmp_free(dec, strlen(dec) + 1);
  mpz_clear(z);
  return out;
}

/* The reference natShowStr: which nats render as readable strings. */
static bool cn_str_byte_ok(uint8_t b) {
  if (b == '\n')
    return true;
  if (b == '"')
    return false;
  return b >= 0x20 && b < 0x7f;
}

static bool cn_nat_is_str(pl_val v) {
  size_t n = pl_nat_byte_len(v);
  if (n == 0)
    return false;
  if (n == 1) {
    uint8_t b = pl_nat_byte_at(v, 0);
    return (b >= 'a' && b <= 'z') || (b >= 'A' && b <= 'Z') || b == '_';
  }
  for (size_t i = 0; i < n; i++) {
    if (!cn_str_byte_ok(pl_nat_byte_at(v, i)))
      return false;
  }
  return true;
}

/* Haskell `show` for the restricted string alphabet: only backslash and
 * newline need escaping (double quotes never pass natShowStr). */
static const char* cn_str_show(cn* c, pl_val v) {
  size_t n = pl_nat_byte_len(v);
  char* out = cn_alloc(c, 2 * n + 3);
  char* p = out;
  *p++ = '"';
  for (size_t i = 0; i < n; i++) {
    uint8_t b = pl_nat_byte_at(v, i);
    if (b == '\\') {
      *p++ = '\\';
      *p++ = '\\';
    } else if (b == '\n') {
      *p++ = '\\';
      *p++ = 'n';
    } else {
      *p++ = (char)b;
    }
  }
  *p++ = '"';
  *p = '\0';
  return out;
}

/* tagName: the readable name of a law tag, or NULL. */
static const char* cn_tag_name(cn* c, pl_val tag) {
  return pl_nat_to_cstr(ax_arena_as_allocator(c->ar), tag);
}

/* ── Pass 1: extract (with nameSelf fused) ─────────────────────────────── */

static cn_doc* cn_extract(cn* c, pl_val v);

static cn_doc* cn_doc_new(cn* c, cn_dkind k) {
  cn_doc* d = cn_alloc(c, sizeof(cn_doc));
  memset(d, 0, sizeof(*d));
  d->k = k;
  return d;
}

static cn_expr* cn_expr_new(cn* c, cn_ekind k) {
  cn_expr* e = cn_alloc(c, sizeof(cn_expr));
  memset(e, 0, sizeof(*e));
  e->k = k;
  return e;
}

static cn_ref* cn_ref_new(cn* c, cn_refkind rk) {
  cn_ref* r = cn_alloc(c, sizeof(cn_ref));
  memset(r, 0, sizeof(*r));
  r->rk = rk;
  return r;
}

/* Is v the 2-ary application (n x y)? */
static pl_cell* cn_as_app2(pl_val v, uint64_t head) {
  pl_cell* p = pl_as(PL_TAG_APP, v);
  if (p != NULL && pl_app_head(p) == head && pl_app_n(p) == 2)
    return p;
  return NULL;
}

static cn_expr* cn_extract_expr(cn* c, cn_law* law, uint64_t maxref, pl_val v) {
  /* goApp: peel the binary (0 f x) application spine */
  pl_val* xs = NULL; /* stb_ds; outermost arg first */
  pl_cell* p;
  while ((p = cn_as_app2(v, 0)) != NULL) {
    ax_arrpush(xs, pl_app_args(p)[1]);
    v = pl_app_args(p)[0];
  }

  /* goHead */
  cn_expr* e;
  pl_cell* ap = pl_as(PL_TAG_APP, v);
  if (pl_is_nat63(v) && v <= maxref) {
    e = cn_expr_new(c, CN_EVAR);
    if (v == 0) {
      e->ref = law->self;
    } else {
      e->ref = cn_ref_new(c, CN_RVAR);
      e->ref->var = v;
    }
  } else if (ap != NULL && pl_app_head(ap) == 0 && pl_app_n(ap) == 1) {
    e = cn_expr_new(c, CN_ECONST);
    e->doc = cn_extract(c, pl_app_args(ap)[0]);
  } else {
    e = cn_expr_new(c, CN_EESC);
    e->doc = cn_extract(c, v);
  }

  /* foldl EApp over the collected args (innermost-first application) */
  for (size_t i = ax_arrlenu(xs); i > 0; i--) {
    cn_expr* app = cn_expr_new(c, CN_EAPP);
    app->f = e;
    app->x = cn_extract_expr(c, law, maxref, xs[i - 1]);
    e = app;
  }
  ax_arrfree(xs);
  return e;
}

static cn_law* cn_extract_law(cn* c, uint64_t arity, pl_val tag, pl_val body) {
  cn_law* law = cn_alloc(c, sizeof(cn_law));
  memset(law, 0, sizeof(*law));

  /* peelLets: unwind the (1 v k) chain */
  pl_val* letvals = NULL;
  pl_cell* p;
  while ((p = cn_as_app2(body, 1)) != NULL) {
    ax_arrpush(letvals, pl_app_args(p)[0]);
    body = pl_app_args(p)[1];
  }
  size_t nlets = ax_arrlenu(letvals);
  uint64_t maxref = arity + nlets;

  law->tag = cn_extract(c, tag);
  const char* hint = cn_tag_name(c, tag);
  law->self = cn_ref_new(c, CN_RSELF);
  law->self->name = hint != NULL ? hint : "self";

  law->nargs = (size_t)arity;
  law->args = cn_alloc(c, sizeof(cn_ref*) * (arity ? (size_t)arity : 1));
  for (uint64_t i = 1; i <= arity; i++) {
    cn_ref* r = cn_ref_new(c, CN_RVAR);
    r->var = i;
    law->args[i - 1] = r;
  }

  law->nlets = nlets;
  law->lets = cn_alloc(c, sizeof(cn_ref*) * (nlets ? nlets : 1));
  law->rhss = cn_alloc(c, sizeof(cn_expr*) * (nlets ? nlets : 1));
  for (size_t j = 0; j < nlets; j++) {
    cn_ref* r = cn_ref_new(c, CN_RVAR);
    r->var = arity + 1 + j;
    law->lets[j] = r;
    law->rhss[j] = cn_extract_expr(c, law, maxref, letvals[j]);
  }
  law->body = cn_extract_expr(c, law, maxref, body);
  ax_arrfree(letvals);
  return law;
}

static cn_doc* cn_extract(cn* c, pl_val v) {
  if (pl_is_nat(v)) {
    cn_doc* d = cn_doc_new(c, cn_nat_is_str(v) ? CN_DSTR : CN_DNUM);
    d->nat = v;
    return d;
  }
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_PIN: {
    pl_val body = pl_pin_body(p);
    if (!pl_pin_is_hashed(v))
      return cn_doc_new(c, CN_DLIQUID);
    if (pl_is_nat(body)) {
      cn_doc* d = cn_doc_new(c, CN_DPIN);
      d->inner = cn_extract(c, body);
      return d;
    }
    cn_doc* d = cn_doc_new(c, CN_DREF);
    d->ref = cn_ref_new(c, CN_RPIN);
    d->ref->pin = v;
    pl_cell* bp = pl_as(PL_TAG_LAW, body);
    d->ref->hint = bp != NULL ? cn_tag_name(c, pl_law_name(bp)) : NULL;
    return d;
  }
  case PL_TAG_LAW: {
    cn_doc* d = cn_doc_new(c, CN_DLAW);
    d->law = cn_extract_law(c, pl_law_arity(p), pl_law_name(p), pl_law_body(p));
    return d;
  }
  case PL_TAG_APP: {
    cn_doc* d = cn_doc_new(c, CN_DAPP);
    uint32_t n = pl_app_n(p);
    d->head = cn_extract(c, pl_app_head(p));
    d->nargs = n;
    d->args = cn_alloc(c, sizeof(cn_doc*) * n);
    for (uint32_t i = 0; i < n; i++)
      d->args[i] = cn_extract(c, pl_app_args(p)[i]);
    return d;
  }
  default:
    ax_abort("canon: non-normal value (tag 0x%llx)",
             (unsigned long long)pl_tag(v));
  }
}

/* ── Pass 2: collect globals + self names (orderedGlobals order) ───────── */

static bool cn_name_used(cn* c, const char* name) {
  for (size_t i = 0; i < ax_arrlenu(c->used); i++) {
    if (strcmp(c->used[i], name) == 0)
      return true;
  }
  return false;
}

static void cn_collect_expr(cn* c, cn_expr* e);

static void cn_collect_doc(cn* c, cn_doc* d) {
  switch (d->k) {
  case CN_DNUM:
  case CN_DSTR:
  case CN_DLIQUID:
    return;
  case CN_DPIN:
    cn_collect_doc(c, d->inner);
    return;
  case CN_DREF:
    if (d->ref->rk == CN_RPIN && ax_hmgeti(c->pinidx, d->ref->pin) < 0) {
      ax_hmput(c->pinidx, d->ref->pin, ax_arrlenu(c->globals));
      cn_global g = {.pin = d->ref->pin, .hint = d->ref->hint, .name = NULL};
      ax_base58(pl_pin_hash(d->ref->pin), 32, g.b58);
      ax_arrpush(c->globals, g);
    }
    return;
  case CN_DAPP:
    cn_collect_doc(c, d->head);
    for (size_t i = 0; i < d->nargs; i++)
      cn_collect_doc(c, d->args[i]);
    return;
  case CN_DLAW: {
    /* the law always reserves its self name (nameSelf's allRefs) */
    if (!cn_name_used(c, d->law->self->name))
      ax_arrpush(c->used, d->law->self->name);
    cn_collect_doc(c, d->law->tag);
    for (size_t j = 0; j < d->law->nlets; j++)
      cn_collect_expr(c, d->law->rhss[j]);
    cn_collect_expr(c, d->law->body);
    return;
  }
  }
}

static void cn_collect_expr(cn* c, cn_expr* e) {
  switch (e->k) {
  case CN_EVAR:
    return;
  case CN_EAPP:
    cn_collect_expr(c, e->f);
    cn_collect_expr(c, e->x);
    return;
  case CN_ECONST:
  case CN_EESC:
    cn_collect_doc(c, e->doc);
    return;
  }
}

/* ── Pass 3: assignGlobalNames ─────────────────────────────────────────── */

static const char* cn_fresh_name(cn* c, const char* base) {
  if (!cn_name_used(c, base)) {
    ax_arrpush(c->used, base);
    return base;
  }
  for (int i = 2;; i++) {
    char buf[256];
    snprintf(buf, sizeof(buf), "%s_%d", base, i);
    if (!cn_name_used(c, buf)) {
      const char* name = cn_strdup_n(c, buf, strlen(buf));
      ax_arrpush(c->used, name);
      return name;
    }
  }
}

static int cn_global_order(const void* pa, const void* pb) {
  const cn_global* const* a = pa;
  const cn_global* const* b = pb;
  int byname = strcmp((*a)->hint, (*b)->hint);
  if (byname != 0)
    return byname;
  return memcmp(pl_pin_hash((*a)->pin), pl_pin_hash((*b)->pin), 32);
}

static int cn_hash_order(const void* pa, const void* pb) {
  const cn_global* const* a = pa;
  const cn_global* const* b = pb;
  return memcmp(pl_pin_hash((*a)->pin), pl_pin_hash((*b)->pin), 32);
}

static void cn_assign_global_names(cn* c) {
  cn_global** named = NULL;
  cn_global** unnamed = NULL;
  for (size_t i = 0; i < ax_arrlenu(c->globals); i++) {
    if (c->globals[i].hint != NULL)
      ax_arrpush(named, &c->globals[i]);
    else
      ax_arrpush(unnamed, &c->globals[i]);
  }
  if (ax_arrlenu(named) > 0)
    qsort(named, ax_arrlenu(named), sizeof(cn_global*), cn_global_order);
  if (ax_arrlenu(unnamed) > 0)
    qsort(unnamed, ax_arrlenu(unnamed), sizeof(cn_global*), cn_hash_order);

  for (size_t i = 0; i < ax_arrlenu(named); i++)
    named[i]->name = cn_fresh_name(c, named[i]->hint);
  for (size_t i = 0; i < ax_arrlenu(unnamed); i++) {
    char base[16];
    snprintf(base, sizeof(base), "<%.8s>", unnamed[i]->b58);
    unnamed[i]->name = cn_fresh_name(c, cn_strdup_n(c, base, strlen(base)));
  }
  ax_arrfree(named);
  ax_arrfree(unnamed);
}

/* Second walk: resolve every pin ref to its assigned global name (this
 * one descends into DPin so no ref is left unnamed). */
static void cn_resolve_expr(cn* c, cn_expr* e);

static void cn_resolve_doc(cn* c, cn_doc* d) {
  switch (d->k) {
  case CN_DNUM:
  case CN_DSTR:
  case CN_DLIQUID:
    return;
  case CN_DPIN:
    cn_resolve_doc(c, d->inner);
    return;
  case CN_DREF:
    if (d->ref->rk == CN_RPIN) {
      ptrdiff_t i = ax_hmgeti(c->pinidx, d->ref->pin);
      ax_assume(i >= 0, "canon: unresolved pin ref");
      d->ref->name = c->globals[c->pinidx[i].value].name;
    }
    return;
  case CN_DAPP:
    cn_resolve_doc(c, d->head);
    for (size_t i = 0; i < d->nargs; i++)
      cn_resolve_doc(c, d->args[i]);
    return;
  case CN_DLAW:
    cn_resolve_doc(c, d->law->tag);
    for (size_t j = 0; j < d->law->nlets; j++)
      cn_resolve_expr(c, d->law->rhss[j]);
    cn_resolve_expr(c, d->law->body);
    return;
  }
}

static void cn_resolve_expr(cn* c, cn_expr* e) {
  switch (e->k) {
  case CN_EVAR:
    return;
  case CN_EAPP:
    cn_resolve_expr(c, e->f);
    cn_resolve_expr(c, e->x);
    return;
  case CN_ECONST:
  case CN_EESC:
    cn_resolve_doc(c, e->doc);
    return;
  }
}

/* ── Pass 4: nameVars ──────────────────────────────────────────────────── */

static const char* cn_gen_local(cn* c, int i) {
  char tmp[16];
  int p = (int)sizeof(tmp);
  tmp[--p] = (char)('a' + i % 26);
  i = i / 26 - 1;
  while (i >= 0) {
    tmp[--p] = (char)('a' + i % 26);
    i = i / 26 - 1;
  }
  return cn_strdup_n(c, tmp + p, sizeof(tmp) - (size_t)p);
}

static const char* cn_next_fresh(cn* c) {
  for (;;) {
    const char* name = cn_gen_local(c, c->nc);
    if (!cn_name_used(c, name)) {
      c->nc++;
      return name;
    }
    c->nc++;
  }
}

typedef struct cn_local {
  uint64_t key; /* var index */
  const char* value;
} cn_local;

static void cn_namevars_doc(cn* c, cn_doc* d);

static void cn_namevars_expr(cn* c, cn_local* tbl, cn_expr* e) {
  switch (e->k) {
  case CN_EVAR:
    if (e->ref->rk == CN_RVAR) {
      ptrdiff_t i = ax_hmgeti(tbl, e->ref->var);
      ax_assume(i >= 0, "canon: unbound law variable");
      e->ref->name = tbl[i].value;
    }
    return;
  case CN_EAPP:
    cn_namevars_expr(c, tbl, e->f);
    cn_namevars_expr(c, tbl, e->x);
    return;
  case CN_ECONST:
  case CN_EESC:
    cn_namevars_doc(c, e->doc);
    return;
  }
}

static void cn_namevars_doc(cn* c, cn_doc* d) {
  switch (d->k) {
  case CN_DNUM:
  case CN_DSTR:
  case CN_DREF:
  case CN_DLIQUID:
    return;
  case CN_DPIN:
    cn_namevars_doc(c, d->inner);
    return;
  case CN_DAPP:
    cn_namevars_doc(c, d->head);
    for (size_t i = 0; i < d->nargs; i++)
      cn_namevars_doc(c, d->args[i]);
    return;
  case CN_DLAW: {
    cn_law* law = d->law;
    cn_namevars_doc(c, law->tag);
    cn_local* tbl = NULL;
    ax_hmput(tbl, (uint64_t)0, law->self->name);
    for (size_t i = 0; i < law->nargs; i++) {
      law->args[i]->name = cn_next_fresh(c);
      ax_hmput(tbl, law->args[i]->var, law->args[i]->name);
    }
    for (size_t j = 0; j < law->nlets; j++) {
      law->lets[j]->name = cn_next_fresh(c);
      ax_hmput(tbl, law->lets[j]->var, law->lets[j]->name);
    }
    for (size_t j = 0; j < law->nlets; j++)
      cn_namevars_expr(c, tbl, law->rhss[j]);
    cn_namevars_expr(c, tbl, law->body);
    ax_hmfree(tbl);
    return;
  }
  }
}

/* ── Renderer ──────────────────────────────────────────────────────────── */

static const char* cn_pp(cn* c, int col, cn_doc* d);
static const char* cn_pp_flat(cn* c, cn_doc* d);
static const char* cn_pp_wide(cn* c, int col, cn_doc* d);
static const char* cn_flat_expr(cn* c, cn_expr* e);
static const char* cn_wide_expr(cn* c, int ec, cn_expr* e);

static bool cn_is_delimited(const char* s) {
  return s[0] == '(' || s[0] == '[' || s[0] == '{';
}

static const char* cn_wrap(cn* c, const char* s) {
  if (s[0] == '(')
    return s;
  return CN_CAT(c, "(", s, ")");
}

/* ── Flat ── */

static const char* cn_flat_law(cn* c, cn_law* law) {
  ax_sb sb;
  cn_sb_init(&sb);
  ax_sb_append_lit(&sb, "(#law ");
  cn_sb_append_cstr(&sb, "cn_flat_law tag", cn_pp_flat(c, law->tag));
  ax_sb_append_lit(&sb, " (");
  cn_sb_append_cstr(&sb, "cn_flat_law self", law->self->name);
  for (size_t i = 0; i < law->nargs; i++) {
    ax_sb_append_lit(&sb, " ");
    cn_sb_append_cstr(&sb, "cn_flat_law arg", law->args[i]->name);
  }
  ax_sb_append_lit(&sb, ")");
  for (size_t j = 0; j < law->nlets; j++) {
    ax_sb_append_lit(&sb, " ");
    cn_sb_append_cstr(&sb, "cn_flat_law let", law->lets[j]->name);
    cn_sb_append_cstr(&sb, "cn_flat_law rhs",
                      cn_wrap(c, cn_flat_expr(c, law->rhss[j])));
  }
  ax_sb_append_lit(&sb, " ");
  cn_sb_append_cstr(&sb, "cn_flat_law body", cn_flat_expr(c, law->body));
  ax_sb_append_lit(&sb, ")");
  return cn_sb_build_flat(c, &sb, "cn_flat_law build");
}

static const char* cn_pp_flat(cn* c, cn_doc* d) {
  switch (d->k) {
  case CN_DNUM:
    return cn_num_str(c, d->nat);
  case CN_DSTR:
    return cn_str_show(c, d->nat);
  case CN_DREF:
    return cn_cstr("cn_pp_flat DREF", d->ref->name);
  case CN_DPIN:
    return CN_CAT(c, "(#pin ", cn_pp_flat(c, d->inner), ")");
  case CN_DLIQUID:
    return "liquid";
  case CN_DLAW:
    return cn_flat_law(c, d->law);
  case CN_DAPP: {
    /* "(" f " " unwords(args) ")" — the space after the head is emitted
     * even for zero args, matching the reference layout exactly */
    ax_sb sb;
    cn_sb_init(&sb);
    ax_sb_append_lit(&sb, "(");
    cn_sb_append_cstr(&sb, "cn_pp_flat app head", cn_pp_flat(c, d->head));
    ax_sb_append_lit(&sb, " ");
    for (size_t i = 0; i < d->nargs; i++) {
      if (i > 0)
        ax_sb_append_lit(&sb, " ");
      cn_sb_append_cstr(&sb, "cn_pp_flat app arg", cn_pp_flat(c, d->args[i]));
    }
    ax_sb_append_lit(&sb, ")");
    return cn_sb_build_flat(c, &sb, "cn_pp_flat app build");
  }
  }
  ax_abort("canon: bad doc kind");
}

/* Peel an EApp spine into (head, args in application order). */
static cn_expr* cn_expr_spine(cn_expr* e, cn_expr*** out_args, size_t* out_n) {
  cn_expr** acc = NULL;
  while (e->k == CN_EAPP) {
    ax_arrpush(acc, e->x);
    e = e->f;
  }
  /* acc is innermost-last; reverse to application order */
  size_t n = ax_arrlenu(acc);
  for (size_t i = 0; i < n / 2; i++) {
    cn_expr* t = acc[i];
    acc[i] = acc[n - 1 - i];
    acc[n - 1 - i] = t;
  }
  *out_args = acc;
  *out_n = n;
  return e;
}

static const char* cn_flat_head(cn* c, cn_expr* hd) {
  switch (hd->k) {
  case CN_EVAR:
    return cn_cstr("cn_flat_head EVAR", hd->ref->name);
  case CN_ECONST:
    if (hd->doc->k == CN_DAPP) {
      ax_sb sb;
      cn_sb_init(&sb);
      ax_sb_append_lit(&sb, "(#app ");
      cn_sb_append_cstr(&sb, "cn_flat_head app head",
                        cn_pp_flat(c, hd->doc->head));
      for (size_t i = 0; i < hd->doc->nargs; i++) {
        ax_sb_append_lit(&sb, " ");
        cn_sb_append_cstr(&sb, "cn_flat_head app arg",
                          cn_pp_flat(c, hd->doc->args[i]));
      }
      ax_sb_append_lit(&sb, ")");
      return cn_sb_build_flat(c, &sb, "cn_flat_head build");
    }
    return cn_pp_flat(c, hd->doc);
  case CN_EESC: {
    const char* s = cn_pp_flat(c, hd->doc);
    if (cn_is_delimited(s))
      return CN_CAT(c, "#", s);
    return CN_CAT(c, "#(", s, ")");
  }
  case CN_EAPP:
    ax_abort("canon: EApp at expr head");
  }
  ax_abort("canon: bad expr kind");
}

static const char* cn_flat_expr(cn* c, cn_expr* e) {
  cn_expr** args;
  size_t n;
  cn_expr* hd = cn_expr_spine(e, &args, &n);
  if (n == 0) {
    ax_arrfree(args);
    return cn_flat_head(c, hd);
  }
  ax_sb sb;
  cn_sb_init(&sb);
  ax_sb_append_lit(&sb, "(");
  cn_sb_append_cstr(&sb, "cn_flat_expr head", cn_flat_head(c, hd));
  for (size_t i = 0; i < n; i++) {
    ax_sb_append_lit(&sb, " ");
    cn_sb_append_cstr(&sb, "cn_flat_expr arg", cn_flat_expr(c, args[i]));
  }
  ax_sb_append_lit(&sb, ")");
  ax_arrfree(args);
  return cn_sb_build_flat(c, &sb, "cn_flat_expr build");
}

/* ── Wide ── */

static const char* cn_pp(cn* c, int col, cn_doc* d) {
  size_t mark = cn_arena_mark(c);
  const char* flat = cn_pp_flat(c, d);
  if (cn_strlen("cn_pp flat", flat) <= (size_t)c->maxw)
    return flat;
  cn_arena_rewind(c, mark);
  return cn_pp_wide(c, col, d);
}

/* Greedily take docs while their flat rendering fits the budget. */
static size_t cn_take_fitting(cn* c, long budget, cn_doc** xs, size_t n,
                              const char*** out_flats) {
  const char** flats = NULL;
  size_t taken = 0;
  while (taken < n) {
    size_t mark = cn_arena_mark(c);
    const char* flat = cn_pp_flat(c, xs[taken]);
    long len = (long)cn_strlen("cn_take_fitting flat", flat);
    if (len > budget) {
      cn_arena_rewind(c, mark);
      break;
    }
    ax_arrpush(flats, flat);
    budget -= len + 1;
    taken++;
  }
  *out_flats = flats;
  return taken;
}

static const char* cn_pack_lines(cn* c, int col, cn_doc** xs, size_t n) {
  ax_sb sb;
  cn_sb_init(&sb);
  size_t i = 0;
  while (i < n) {
    const char** flats;
    size_t taken = cn_take_fitting(c, c->maxw - col, xs + i, n - i, &flats);
    cn_sb_append_cstr(&sb, "cn_pack_lines newline", cn_nl(c, col));
    if (taken == 0) {
      cn_sb_append_cstr(&sb, "cn_pack_lines wide", cn_pp_wide(c, col, xs[i]));
      i += 1;
    } else {
      for (size_t j = 0; j < taken; j++) {
        if (j > 0)
          ax_sb_append_lit(&sb, " ");
        cn_sb_append_cstr(&sb, "cn_pack_lines flat", flats[j]);
      }
      i += taken;
    }
    ax_arrfree(flats);
  }
  return cn_sb_build(c, &sb, "cn_pack_lines build");
}

static const char* cn_wide_app(cn* c, int col, cn_doc* d) {
  int col2 = col + 2;
  const char* sf = cn_cstr("cn_wide_app head", cn_pp(c, col + 1, d->head));
  long budget = c->maxw - col2 - (long)cn_strlen("cn_wide_app head", sf);

  ax_sb sb;
  cn_sb_init(&sb);
  ax_sb_append_lit(&sb, "(");
  cn_sb_append_cstr(&sb, "cn_wide_app head", sf);

  const char** flats;
  size_t taken = cn_take_fitting(c, budget, d->args, d->nargs, &flats);
  if (taken == 0 && d->nargs > 0) {
    cn_sb_append_cstr(&sb, "cn_wide_app newline", cn_nl(c, col2));
    cn_sb_append_cstr(&sb, "cn_wide_app first wide",
                      cn_pp_wide(c, col2, d->args[0]));
    cn_sb_append_cstr(&sb, "cn_wide_app rest",
                      cn_pack_lines(c, col2, d->args + 1, d->nargs - 1));
  } else if (taken > 0) {
    ax_sb_append_lit(&sb, " ");
    for (size_t j = 0; j < taken; j++) {
      if (j > 0)
        ax_sb_append_lit(&sb, " ");
      cn_sb_append_cstr(&sb, "cn_wide_app flat", flats[j]);
    }
    cn_sb_append_cstr(
        &sb, "cn_wide_app rest",
        cn_pack_lines(c, col2, d->args + taken, d->nargs - taken));
  }
  ax_arrfree(flats);
  ax_sb_append_lit(&sb, ")");
  return cn_sb_build(c, &sb, "cn_wide_app build");
}

static const char* cn_wide_head(cn* c, int ec, cn_expr* hd) {
  switch (hd->k) {
  case CN_EVAR:
    return cn_cstr("cn_wide_head EVAR", hd->ref->name);
  case CN_ECONST:
    if (hd->doc->k == CN_DAPP) {
      size_t mark = cn_arena_mark(c);
      const char* flat = cn_flat_head(c, hd);
      if (ec + (long)cn_strlen("cn_wide_head flat", flat) <= (long)c->maxw)
        return flat;
      cn_arena_rewind(c, mark);
      int col2 = ec + 2;
      ax_sb sb;
      cn_sb_init(&sb);
      ax_sb_append_lit(&sb, "(#app ");
      cn_sb_append_cstr(&sb, "cn_wide_head app head",
                        cn_pp(c, ec + 6, hd->doc->head));
      for (size_t i = 0; i < hd->doc->nargs; i++) {
        cn_sb_append_cstr(&sb, "cn_wide_head newline", cn_nl(c, col2));
        cn_sb_append_cstr(&sb, "cn_wide_head app arg",
                          cn_pp(c, col2, hd->doc->args[i]));
      }
      ax_sb_append_lit(&sb, ")");
      return cn_sb_build(c, &sb, "cn_wide_head build");
    }
    return cn_pp(c, ec, hd->doc);
  case CN_EESC: {
    const char* s = cn_pp_flat(c, hd->doc);
    if (cn_is_delimited(s))
      return CN_CAT(c, "#", cn_pp(c, ec + 1, hd->doc));
    return CN_CAT(c, "#(", cn_pp(c, ec + 2, hd->doc), ")");
  }
  case CN_EAPP:
    ax_abort("canon: EApp at expr head");
  }
  ax_abort("canon: bad expr kind");
}

static size_t cn_take_exprs(cn* c, long budget, cn_expr** xs, size_t n,
                            const char*** out_flats) {
  const char** flats = NULL;
  size_t taken = 0;
  while (taken < n) {
    size_t mark = cn_arena_mark(c);
    const char* flat = cn_flat_expr(c, xs[taken]);
    long len = (long)cn_strlen("cn_take_exprs flat", flat);
    if (len > budget) {
      cn_arena_rewind(c, mark);
      break;
    }
    ax_arrpush(flats, flat);
    budget -= len + 1;
    taken++;
  }
  *out_flats = flats;
  return taken;
}

static const char* cn_pack_exprs(cn* c, int col, cn_expr** xs, size_t n) {
  ax_sb sb;
  cn_sb_init(&sb);
  size_t i = 0;
  while (i < n) {
    const char** flats;
    size_t taken = cn_take_exprs(c, c->maxw - col, xs + i, n - i, &flats);
    cn_sb_append_cstr(&sb, "cn_pack_exprs newline", cn_nl(c, col));
    if (taken == 0) {
      cn_sb_append_cstr(&sb, "cn_pack_exprs wide", cn_wide_expr(c, col, xs[i]));
      i += 1;
    } else {
      for (size_t j = 0; j < taken; j++) {
        if (j > 0)
          ax_sb_append_lit(&sb, " ");
        cn_sb_append_cstr(&sb, "cn_pack_exprs flat", flats[j]);
      }
      i += taken;
    }
    ax_arrfree(flats);
  }
  return cn_sb_build(c, &sb, "cn_pack_exprs build");
}

static const char* cn_wide_expr(cn* c, int ec, cn_expr* e) {
  cn_expr** args;
  size_t n;
  cn_expr* hd = cn_expr_spine(e, &args, &n);
  if (n == 0) {
    ax_arrfree(args);
    return cn_wide_head(c, ec, hd);
  }

  /* try flat first */
  {
    size_t mark = cn_arena_mark(c);
    ax_sb sb;
    cn_sb_init(&sb);
    ax_sb_append_lit(&sb, "(");
    cn_sb_append_cstr(&sb, "cn_wide_expr flat head", cn_flat_head(c, hd));
    for (size_t i = 0; i < n; i++) {
      ax_sb_append_lit(&sb, " ");
      cn_sb_append_cstr(&sb, "cn_wide_expr flat arg", cn_flat_expr(c, args[i]));
    }
    ax_sb_append_lit(&sb, ")");
    const char* flat = cn_sb_build_flat(c, &sb, "cn_wide_expr flat build");
    if (cn_strlen("cn_wide_expr flat", flat) <= (size_t)c->maxw) {
      ax_arrfree(args);
      return flat;
    }
    cn_arena_rewind(c, mark);
  }

  int col2 = ec + 2;
  const char* sh = cn_wide_head(c, ec + 1, hd);
  long budget = c->maxw - col2 - (long)cn_strlen("cn_wide_expr head", sh);

  ax_sb sb;
  cn_sb_init(&sb);
  ax_sb_append_lit(&sb, "(");
  cn_sb_append_cstr(&sb, "cn_wide_expr head", sh);

  const char** flats;
  size_t taken = cn_take_exprs(c, budget, args, n, &flats);
  if (taken == 0 && n > 0) {
    cn_sb_append_cstr(&sb, "cn_wide_expr newline", cn_nl(c, col2));
    cn_sb_append_cstr(&sb, "cn_wide_expr first wide",
                      cn_wide_expr(c, col2, args[0]));
    cn_sb_append_cstr(&sb, "cn_wide_expr rest",
                      cn_pack_exprs(c, col2, args + 1, n - 1));
  } else if (taken > 0) {
    ax_sb_append_lit(&sb, " ");
    for (size_t j = 0; j < taken; j++) {
      if (j > 0)
        ax_sb_append_lit(&sb, " ");
      cn_sb_append_cstr(&sb, "cn_wide_expr flat", flats[j]);
    }
    cn_sb_append_cstr(&sb, "cn_wide_expr rest",
                      cn_pack_exprs(c, col2, args + taken, n - taken));
  }
  ax_arrfree(flats);
  ax_arrfree(args);
  ax_sb_append_lit(&sb, ")");
  return cn_sb_build(c, &sb, "cn_wide_expr build");
}

static const char* cn_wide_law(cn* c, int col, cn_law* law) {
  int col2 = col + 2;

  ax_sb sig;
  cn_sb_init(&sig);
  ax_sb_append_lit(&sig, "(");
  cn_sb_append_cstr(&sig, "cn_wide_law self", law->self->name);
  for (size_t i = 0; i < law->nargs; i++) {
    ax_sb_append_lit(&sig, " ");
    cn_sb_append_cstr(&sig, "cn_wide_law arg", law->args[i]->name);
  }
  ax_sb_append_lit(&sig, ")");
  const char* sig_s = cn_sb_build(c, &sig, "cn_wide_law sig build");

  const char* header =
      CN_CAT(c, "(#law ", cn_pp(c, col + 6, law->tag), " ", sig_s);

  size_t flat_body_mark = cn_arena_mark(c);
  ax_sb fb;
  cn_sb_init(&fb);
  for (size_t j = 0; j < law->nlets; j++) {
    ax_sb_append_lit(&fb, " ");
    cn_sb_append_cstr(&fb, "cn_wide_law flat let", law->lets[j]->name);
    cn_sb_append_cstr(&fb, "cn_wide_law flat rhs",
                      cn_wrap(c, cn_flat_expr(c, law->rhss[j])));
  }
  ax_sb_append_lit(&fb, " ");
  cn_sb_append_cstr(&fb, "cn_wide_law flat body", cn_flat_expr(c, law->body));
  const char* flat_body = cn_sb_build_flat(c, &fb, "cn_wide_law body build");

  if (col + (long)cn_strlen("cn_wide_law header", header) +
          (long)cn_strlen("cn_wide_law flat_body", flat_body) + 1 <=
      (long)c->maxw)
    return CN_CAT(c, header, flat_body, ")");
  cn_arena_rewind(c, flat_body_mark);

  ax_sb sb;
  cn_sb_init(&sb);
  cn_sb_append_cstr(&sb, "cn_wide_law header", header);
  for (size_t j = 0; j < law->nlets; j++) {
    cn_sb_append_cstr(&sb, "cn_wide_law newline", cn_nl(c, col2));
    cn_sb_append_cstr(&sb, "cn_wide_law let", law->lets[j]->name);
    const char* e = cn_wide_expr(
        c, col2 + (int)cn_strlen("cn_wide_law let name", law->lets[j]->name),
        law->rhss[j]);
    if (e[0] == '(') {
      cn_sb_append_cstr(&sb, "cn_wide_law rhs", e);
    } else {
      ax_sb_append_lit(&sb, "(");
      cn_sb_append_cstr(&sb, "cn_wide_law rhs", e);
      ax_sb_append_lit(&sb, ")");
    }
  }
  cn_sb_append_cstr(&sb, "cn_wide_law body newline", cn_nl(c, col2));
  cn_sb_append_cstr(&sb, "cn_wide_law body", cn_wide_expr(c, col2, law->body));
  ax_sb_append_lit(&sb, ")");
  return cn_sb_build(c, &sb, "cn_wide_law build");
}

static const char* cn_pp_wide(cn* c, int col, cn_doc* d) {
  switch (d->k) {
  case CN_DNUM:
    return cn_num_str(c, d->nat);
  case CN_DSTR:
    return cn_str_show(c, d->nat);
  case CN_DREF:
    return cn_cstr("cn_pp_wide DREF", d->ref->name);
  case CN_DPIN:
    return CN_CAT(c, "(#pin ", cn_pp(c, col + 6, d->inner), ")");
  case CN_DLIQUID:
    return "liquid";
  case CN_DLAW:
    return cn_wide_law(c, col, d->law);
  case CN_DAPP:
    return cn_wide_app(c, col, d);
  }
  ax_abort("canon: bad doc kind");
}

/* ── Pipeline / entry points ───────────────────────────────────────────── */

static cn_doc* cn_pipeline(cn* c, pl_val v) {
  cn_doc* doc = cn_extract(c, v);
  cn_collect_doc(c, doc);
  cn_assign_global_names(c);
  cn_resolve_doc(c, doc);
  cn_namevars_doc(c, doc);
  return doc;
}

static cn_doc* cn_ref_doc(cn* c, const char* name) {
  cn_doc* d = cn_doc_new(c, CN_DREF);
  d->ref = cn_ref_new(c, CN_RSELF);
  d->ref->name = name;
  return d;
}

static cn_doc* cn_app1_doc(cn* c, cn_doc* head, cn_doc* a0) {
  cn_doc* d = cn_doc_new(c, CN_DAPP);
  d->head = head;
  d->nargs = 1;
  d->args = cn_alloc(c, sizeof(cn_doc*));
  d->args[0] = a0;
  return d;
}

static char* cn_finish(const ax_allocator* a, const char* s, size_t* out_s) {
  size_t n = strlen(s);
  char* out = ax_calloc(a, char, n + 1);
  ax_assume(out != NULL, "canon: oom");
  memcpy(out, s, n + 1);
  if (out_s != NULL)
    *out_s = n;
  return out;
}

static void cn_free(cn* c) {
  for (size_t i = 0; i < ax_arrlenu(c->temps); i++)
    ax_free(ax_allocator_system(), c->temps[i]);
  ax_arrfree(c->globals);
  ax_hmfree(c->pinidx);
  ax_arrfree(c->used);
  ax_arrfree(c->temps);
  ax_arena_destroy(c->ar);
}

char* pl_show_val(const ax_allocator* a, pl_val v, size_t* out_s) {
  cn c = {.ar = ax_arena_create_overcommit(CN_ARENA_CAP), .maxw = 50};
  ax_assume(c.ar != NULL, "canon: arena");

  cn_doc* top;
  pl_cell* pp = pl_as(PL_TAG_PIN, v);
  if (pp != NULL && !pl_pin_is_hashed(v))
    top = cn_pipeline(&c, v);
  else if (pp != NULL)
    top = cn_app1_doc(&c, cn_ref_doc(&c, "#pin"),
                      cn_pipeline(&c, pl_pin_body(pp)));
  else
    top = cn_pipeline(&c, v);

  char* out = cn_finish(a, cn_pp(&c, 0, top), out_s);
  cn_free(&c);
  return out;
}

char* pl_canonize(const ax_allocator* a, pl_val v, size_t* out_s) {
  cn c = {.ar = ax_arena_create_overcommit(CN_ARENA_CAP), .maxw = 80};
  ax_assume(c.ar != NULL, "canon: arena");

  pl_cell* pp = pl_as(PL_TAG_PIN, v);
  pl_val inner = pp != NULL ? pl_pin_body(pp) : v;
  cn_doc* doc = cn_pipeline(&c, inner);

  ax_sb sb;
  cn_sb_init(&sb);

  size_t maxlen = 0;
  for (size_t i = 0; i < ax_arrlenu(c.globals); i++) {
    size_t l = strlen(c.globals[i].b58);
    if (l > maxlen)
      maxlen = l;
  }
  for (size_t i = 0; i < ax_arrlenu(c.globals); i++) {
    cn_global* g = &c.globals[i];
    ax_sb_append_lit(&sb, "@");
    cn_sb_append_cstr(&sb, "pl_canonize b58", g->b58);
    for (size_t p = strlen(g->b58); p < maxlen; p++)
      ax_sb_append_lit(&sb, " ");
    ax_sb_append_lit(&sb, " (#bind ");
    cn_sb_append_cstr(&sb, "pl_canonize global", g->name);
    ax_sb_append_lit(&sb, " _)\n");
  }

  cn_doc* bind = cn_doc_new(&c, CN_DAPP);
  bind->head = cn_ref_doc(&c, "#bind");
  bind->nargs = 2;
  bind->args = cn_alloc(&c, sizeof(cn_doc*) * 2);
  bind->args[0] = cn_ref_doc(&c, "_");
  bind->args[1] = cn_app1_doc(&c, cn_ref_doc(&c, "#pin"), doc);

  cn_sb_append_cstr(&sb, "pl_canonize body", cn_pp(&c, 0, bind));
  ax_sb_append_lit(&sb, "\n(#export _)\n");

  char* out = cn_finish(a, cn_sb_build(&c, &sb, "pl_canonize build"), out_s);
  cn_free(&c);
  return out;
}
