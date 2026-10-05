#include <ctype.h>
#include <setjmp.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "axsys/allocator.h"
#include "axsys/ds.h"
#include "axsys/sb.h"
#include "plan/debug.h"
#include "plan/eval.h"
#include "plan/heap.h"
#include "plan/nat.h"
#include "plan/store.h"
#include "plan/value.h"

/*
 * scry [--map-size BYTES] STORE-DIR [COMMAND [ARGS...]]
 *
 * Read-only Silo snapshot inspector: walk the root journal, check out
 * any historical snapshot, navigate and pretty-print its value graph,
 * and attribute pins.pack growth to the snapshots that appended it.
 * With a COMMAND it runs once and exits; without one it is a REPL.
 * Attaches alongside a live wisp (MDB_RDONLY + pins.pack O_RDONLY).
 */

#define SCRY_HEAP_CELLS     ((size_t)1 << 20) /* 8 MiB per semispace */
#define SCRY_STORE_MAP_SIZE ((size_t)1 << 30)
#define SCRY_PATH_MAX       512
#define SCRY_SHOW_DEPTH     6
#define SCRY_SHOW_WIDTH     16

typedef struct closure_entry {
  pl_hash key;
  uint64_t value; /* stream length in pins.pack */
} closure_entry;

typedef struct scry_object {
  pl_hash hash;
  uint64_t off;
  uint64_t len;
} scry_object;

typedef struct scry {
  pl_store* store;
  pl_heap* heap;
  pl_thread* thread;
  /* checkout: everything reachable is store-region (non-moving), so the
   * cursor path needs no GC rooting */
  bool loaded;
  uint64_t seq; /* 0: checked out by hash, not via the journal */
  uint8_t root_hash[32];
  pl_val path[SCRY_PATH_MAX];
  size_t path_n;
} scry;

static void hash_hex(const uint8_t* hash, size_t n, char* out) {
  static const char hex[] = "0123456789abcdef";
  for (size_t i = 0; i < n; i++) {
    out[2 * i] = hex[hash[i] >> 4];
    out[2 * i + 1] = hex[hash[i] & 0xf];
  }
  out[2 * n] = '\0';
}

static bool hex_nibble(char c, uint8_t* out) {
  if (c >= '0' && c <= '9')
    *out = (uint8_t)(c - '0');
  else if (c >= 'a' && c <= 'f')
    *out = (uint8_t)(c - 'a' + 10);
  else if (c >= 'A' && c <= 'F')
    *out = (uint8_t)(c - 'A' + 10);
  else
    return false;
  return true;
}

/* Parse an even-length hex prefix; returns bytes parsed, 0 on non-hex. */
static size_t parse_hex(const char* s, uint8_t out[32]) {
  size_t n = strlen(s);
  if (n < 2 || n > 64 || n % 2 != 0)
    return 0;
  for (size_t i = 0; i < n / 2; i++) {
    uint8_t hi, lo;
    if (!hex_nibble(s[2 * i], &hi) || !hex_nibble(s[2 * i + 1], &lo))
      return 0;
    out[i] = (uint8_t)(hi << 4 | lo);
  }
  return n / 2;
}

static bool parse_u64(const char* s, uint64_t* out) {
  if (*s == '\0')
    return false;
  char* end = NULL;
  unsigned long long v = strtoull(s, &end, 10);
  if (end == NULL || *end != '\0')
    return false;
  *out = (uint64_t)v;
  return true;
}

static void fmt_time(uint64_t unix_ns, char* out, size_t cap) {
  time_t secs = (time_t)(unix_ns / 1000000000u);
  struct tm tm;
  if (unix_ns == 0 || localtime_r(&secs, &tm) == NULL) {
    snprintf(out, cap, "-");
    return;
  }
  (void)strftime(out, cap, "%Y-%m-%d %H:%M:%S", &tm);
}

static void fmt_bytes(uint64_t n, char* out, size_t cap) {
  if (n >= (uint64_t)1 << 30)
    snprintf(out, cap, "%.2f GiB", (double)n / (double)((uint64_t)1 << 30));
  else if (n >= (uint64_t)1 << 20)
    snprintf(out, cap, "%.2f MiB", (double)n / (double)((uint64_t)1 << 20));
  else if (n >= (uint64_t)1 << 10)
    snprintf(out, cap, "%.2f KiB", (double)n / (double)((uint64_t)1 << 10));
  else
    snprintf(out, cap, "%llu B", (unsigned long long)n);
}

/* ── journal access ────────────────────────────────────────────────────── */

static pl_store_root_entry* journal_fetch(pl_store* s, size_t* out_n) {
  *out_n = 0;
  uint64_t head = pl_store_root_log_head(s);
  if (head == 0)
    return NULL;
  pl_store_root_entry* entries = malloc((size_t)head * sizeof(*entries));
  if (entries == NULL)
    return NULL;
  *out_n = pl_store_root_log(s, 1, entries, (size_t)head);
  return entries;
}

typedef struct prefix_scan {
  const uint8_t* prefix;
  size_t plen;
  uint8_t hash[32];
  size_t matches;
} prefix_scan;

static void prefix_scan_object(void* ctx, const uint8_t hash[32], uint64_t off,
                               uint64_t len) {
  (void)off;
  (void)len;
  prefix_scan* ps = ctx;
  if (memcmp(hash, ps->prefix, ps->plen) != 0)
    return;
  if (ps->matches == 0 || memcmp(ps->hash, hash, 32) != 0) {
    memcpy(ps->hash, hash, 32);
    ps->matches++;
  }
}

/* Resolve a snapshot argument: a journal sequence number, or a hex hash
 * prefix matched against the journal, the current root, and finally the
 * whole object index (any stored pin is inspectable, not just roots). */
static bool resolve_snapshot(pl_store* s, const char* arg, uint8_t out[32],
                             uint64_t* out_seq) {
  *out_seq = 0;
  size_t n = 0;
  pl_store_root_entry* entries = journal_fetch(s, &n);

  uint64_t seq;
  if (parse_u64(arg, &seq)) {
    bool found = false;
    for (size_t i = 0; i < n; i++) {
      if (entries[i].seq == seq) {
        memcpy(out, entries[i].hash, 32);
        *out_seq = seq;
        found = true;
        break;
      }
    }
    free(entries);
    if (!found)
      fprintf(stderr, "scry: no journal entry with seq %s\n", arg);
    return found;
  }

  uint8_t prefix[32];
  size_t plen = parse_hex(arg, prefix);
  if (plen == 0) {
    free(entries);
    fprintf(stderr, "scry: '%s' is neither a seq nor a hex hash\n", arg);
    return false;
  }
  size_t matches = 0;
  for (size_t i = 0; i < n; i++) {
    if (memcmp(entries[i].hash, prefix, plen) == 0 &&
        (matches == 0 || memcmp(out, entries[i].hash, 32) != 0)) {
      memcpy(out, entries[i].hash, 32);
      *out_seq = entries[i].seq;
      matches++;
    }
  }
  uint8_t current[32];
  if (matches == 0 && pl_store_get_root(s, current) &&
      memcmp(current, prefix, plen) == 0) {
    memcpy(out, current, 32);
    matches = 1;
  }
  if (matches == 0) {
    prefix_scan ps = {.prefix = prefix, .plen = plen};
    (void)pl_store_silo_objects(s, prefix_scan_object, &ps);
    if (ps.matches > 0) {
      memcpy(out, ps.hash, 32);
      matches = ps.matches;
    }
  }
  free(entries);
  if (matches == 0)
    fprintf(stderr, "scry: no snapshot matches '%s'\n", arg);
  else if (matches > 1)
    fprintf(stderr, "scry: '%s' is ambiguous (%zu snapshots)\n", arg, matches);
  return matches == 1;
}

/* ── value navigation ──────────────────────────────────────────────────── */

static pl_val chase(pl_val v) {
  while (!pl_is_nat63(v) && pl_tag(v) == PL_TAG_DEFER &&
         pl_hdr_kind(*pl_ptr(v)) == PL_K_IND)
    v = pl_ind_target(pl_ptr(v));
  return v;
}

static const char* kind_name(pl_val v) {
  if (pl_is_nat(v))
    return "nat";
  switch (pl_tag(v)) {
  case PL_TAG_APP:
    return "app";
  case PL_TAG_LAW:
    return "law";
  case PL_TAG_PIN:
    return "pin";
  case PL_TAG_ENV:
    return "env";
  default:
    return "opaque";
  }
}

static size_t child_count(pl_val v) {
  v = chase(v);
  if (pl_is_nat(v))
    return 0;
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_APP:
    return 1 + (size_t)pl_app_n(p); /* head, then arguments */
  case PL_TAG_LAW:
    return 2; /* name, body */
  case PL_TAG_PIN:
    return 1; /* body */
  default:
    return 0;
  }
}

static pl_val child_at(pl_val v, size_t i) {
  v = chase(v);
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_APP:
    return i == 0 ? pl_app_head(p) : pl_app_args(p)[i - 1];
  case PL_TAG_LAW:
    return i == 0 ? pl_law_name(p) : pl_law_body(p);
  default:
    return pl_pin_body(p);
  }
}

static void print_value(pl_val v, size_t depth, size_t width) {
  ax_sb sb;
  ax_sb_init(&sb, ax_allocator_system());
  pl_show_limited_sb(&sb, v, depth, width);
  size_t n = 0;
  char* text = ax_sb_build(&sb, &n);
  ax_sb_free(&sb);
  /* fwrite, not printf: renderings of binary-ish nats can embed NULs. */
  (void)fwrite(text, 1, n, stdout);
  (void)fputc('\n', stdout);
  ax_free(ax_allocator_system(), text);
}

/* ── closure walks (LMDB index only, no evaluator) ─────────────────────── */

static bool closure_collect(pl_store* s, const uint8_t root[32],
                            closure_entry** set) {
  pl_hash* work = NULL;
  pl_hash first;
  memcpy(first.b, root, 32);
  ax_arrpush(work, first);
  bool ok = true;
  while (ax_arrlen(work) > 0) {
    pl_hash cur = stbds_arrpop(work);
    if (ax_hmgeti(*set, cur) >= 0)
      continue;
    uint64_t len = 0;
    pl_hash* subs = NULL;
    size_t nsub = 0;
    char err[192] = {0};
    if (!pl_store_silo_object_info(s, cur.b, &len, &subs, &nsub, err,
                                   sizeof(err))) {
      char hex[65];
      hash_hex(cur.b, 32, hex);
      fprintf(stderr, "scry: cannot read object %.12s: %s\n", hex, err);
      ok = false;
      break;
    }
    ax_hmput(*set, cur, len);
    for (size_t i = 0; i < nsub; i++)
      ax_arrpush(work, subs[i]);
    free(subs);
  }
  ax_arrfree(work);
  return ok;
}

static uint64_t closure_bytes(closure_entry* set) {
  uint64_t total = 0;
  for (ptrdiff_t i = 0; i < ax_hmlen(set); i++)
    total += set[i].value;
  return total;
}

static int object_len_desc(const void* a, const void* b) {
  const closure_entry* x = a;
  const closure_entry* y = b;
  if (x->value != y->value)
    return x->value < y->value ? 1 : -1;
  return memcmp(x->key.b, y->key.b, 32);
}

/* Sorting an stb_ds hashmap's entry array invalidates its index; callers
 * passing one only free it afterwards. */
static void print_top_objects(closure_entry* objects, size_t n, size_t top) {
  qsort(objects, n, sizeof(*objects), object_len_desc);
  for (size_t i = 0; i < n && i < top; i++) {
    char hex[65], size[32];
    hash_hex(objects[i].key.b, 32, hex);
    fmt_bytes(objects[i].value, size, sizeof(size));
    printf("    %.16s  %s\n", hex, size);
  }
  if (n > top)
    printf("    …+%zu more\n", n - top);
}

/* ── commands ──────────────────────────────────────────────────────────── */

static void cmd_log(scry* sc, const char* arg) {
  uint64_t want = 20;
  if (arg != NULL && !parse_u64(arg, &want)) {
    fprintf(stderr, "scry: log takes a count\n");
    return;
  }
  size_t n = 0;
  pl_store_root_entry* entries = journal_fetch(sc->store, &n);
  if (n == 0) {
    printf("journal is empty (pre-journal store, or no Save yet)\n");
    free(entries);
    return;
  }
  size_t from = n > want ? n - (size_t)want : 0;
  printf("%-5s %-19s %-16s %12s %12s\n", "seq", "time", "root", "pack",
         "delta");
  for (size_t i = from; i < n; i++) {
    char when[32], hex[65], pack[32], delta[32];
    fmt_time(entries[i].unix_ns, when, sizeof(when));
    hash_hex(entries[i].hash, 32, hex);
    fmt_bytes(entries[i].pack_bytes, pack, sizeof(pack));
    if (i == 0)
      fmt_bytes(entries[i].pack_bytes, delta, sizeof(delta));
    else
      fmt_bytes(entries[i].pack_bytes - entries[i - 1].pack_bytes, delta,
                sizeof(delta));
    printf("%-5llu %-19s %.16s %12s %12s\n", (unsigned long long)entries[i].seq,
           when, hex, pack, delta);
  }
  free(entries);
}

static void cmd_root(scry* sc) {
  uint8_t hash[32];
  if (!pl_store_get_root(sc->store, hash)) {
    printf("store has no root\n");
    return;
  }
  char hex[65];
  hash_hex(hash, 32, hex);
  printf("%s\n", hex);
}

static bool load_pin(scry* sc, const uint8_t hash[32], pl_val* out) {
  pl_thread* t = sc->thread;
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    *out = pl_store_load(t, hash);
    pl_catch_pop(t, &c);
    return true;
  }
  pl_catch_unwind(t, &c);
  fprintf(stderr, "scry: %s\n",
          t->exn_msg != NULL ? t->exn_msg : "load raised a PLAN exception");
  return false;
}

static void cmd_co(scry* sc, const char* arg) {
  uint8_t hash[32];
  uint64_t seq = 0;
  if (arg == NULL) {
    if (!pl_store_get_root(sc->store, hash)) {
      fprintf(stderr, "scry: store has no root\n");
      return;
    }
  } else if (!resolve_snapshot(sc->store, arg, hash, &seq)) {
    return;
  }
  pl_val pin = 0;
  if (!load_pin(sc, hash, &pin))
    return;
  sc->loaded = true;
  sc->seq = seq;
  memcpy(sc->root_hash, hash, 32);
  sc->path[0] = pin;
  sc->path_n = 1;
  char hex[65];
  hash_hex(hash, 32, hex);
  if (seq != 0)
    printf("checked out seq %llu (%.16s)\n", (unsigned long long)seq, hex);
  else
    printf("checked out %.16s\n", hex);
  print_value(pl_pin_body(pl_ptr(chase(pin))), 3, 8);
}

static bool need_checkout(scry* sc) {
  if (!sc->loaded)
    fprintf(stderr, "scry: nothing checked out (use: co [seq|hash])\n");
  return sc->loaded;
}

static void cmd_ls(scry* sc) {
  if (!need_checkout(sc))
    return;
  pl_val v = chase(sc->path[sc->path_n - 1]);
  size_t n = child_count(v);
  printf("%s", kind_name(v));
  if (!pl_is_nat(v) && pl_tag(v) == PL_TAG_LAW)
    printf(" arity=%llu", (unsigned long long)pl_law_arity(pl_ptr(v)));
  if (!pl_is_nat(v) && pl_tag(v) == PL_TAG_PIN && pl_pin_hash(v) != NULL) {
    char hex[65];
    hash_hex(pl_pin_hash(v), 32, hex);
    printf(" %.16s", hex);
  }
  printf(", %zu %s\n", n, n == 1 ? "child" : "children");
  for (size_t i = 0; i < n; i++) {
    pl_val child = chase(child_at(v, i));
    printf("  [%zu] %-6s ", i, kind_name(child));
    print_value(child, 2, 6);
  }
}

static void cmd_cd(scry* sc, const char* arg) {
  if (!need_checkout(sc))
    return;
  if (arg == NULL || strcmp(arg, "/") == 0) {
    sc->path_n = 1;
    return;
  }
  if (strcmp(arg, "..") == 0) {
    if (sc->path_n > 1)
      sc->path_n--;
    return;
  }
  uint64_t i;
  pl_val v = sc->path[sc->path_n - 1];
  if (!parse_u64(arg, &i) || i >= child_count(v)) {
    fprintf(stderr, "scry: cd takes .., /, or a child index from ls\n");
    return;
  }
  if (sc->path_n == SCRY_PATH_MAX) {
    fprintf(stderr, "scry: path too deep\n");
    return;
  }
  sc->path[sc->path_n++] = child_at(v, (size_t)i);
}

static void cmd_show(scry* sc, const char* darg, const char* warg) {
  if (!need_checkout(sc))
    return;
  uint64_t depth = SCRY_SHOW_DEPTH, width = SCRY_SHOW_WIDTH;
  if ((darg != NULL && !parse_u64(darg, &depth)) ||
      (warg != NULL && !parse_u64(warg, &width))) {
    fprintf(stderr, "scry: show [depth [width]]\n");
    return;
  }
  print_value(sc->path[sc->path_n - 1], (size_t)depth, (size_t)width);
}

/* Nearest enclosing hashed pin: the cursor if it is one, else walk the
 * path back toward the checkout root. */
static const uint8_t* cursor_pin_hash(scry* sc) {
  for (size_t i = sc->path_n; i > 0; i--) {
    pl_val v = chase(sc->path[i - 1]);
    if (!pl_is_nat(v) && pl_tag(v) == PL_TAG_PIN && pl_pin_hash(v) != NULL)
      return pl_pin_hash(v);
  }
  return NULL;
}

static void cmd_size(scry* sc, const char* arg) {
  uint8_t hash[32];
  if (arg != NULL) {
    uint64_t seq;
    if (!resolve_snapshot(sc->store, arg, hash, &seq))
      return;
  } else {
    if (!need_checkout(sc))
      return;
    const uint8_t* h = cursor_pin_hash(sc);
    if (h == NULL) {
      fprintf(stderr, "scry: no hashed pin at or above the cursor\n");
      return;
    }
    memcpy(hash, h, 32);
  }
  closure_entry* set = NULL;
  if (closure_collect(sc->store, hash, &set)) {
    char total[32], hex[65];
    fmt_bytes(closure_bytes(set), total, sizeof(total));
    hash_hex(hash, 32, hex);
    printf("%.16s: %td pins, %s persisted\n", hex, ax_hmlen(set), total);
    printf("  largest:\n");
    print_top_objects(set, (size_t)ax_hmlen(set), 10);
  }
  ax_hmfree(set);
}

static void cmd_diff(scry* sc, const char* a, const char* b) {
  if (a == NULL || b == NULL) {
    fprintf(stderr, "scry: diff <seq|hash> <seq|hash>\n");
    return;
  }
  uint8_t ha[32], hb[32];
  uint64_t seq;
  if (!resolve_snapshot(sc->store, a, ha, &seq) ||
      !resolve_snapshot(sc->store, b, hb, &seq))
    return;
  closure_entry* ca = NULL;
  closure_entry* cb = NULL;
  if (closure_collect(sc->store, ha, &ca) &&
      closure_collect(sc->store, hb, &cb)) {
    closure_entry* added = NULL;
    uint64_t added_bytes = 0, removed_bytes = 0;
    size_t removed = 0;
    for (ptrdiff_t i = 0; i < ax_hmlen(cb); i++) {
      if (ax_hmgeti(ca, cb[i].key) < 0) {
        ax_arrpush(added, cb[i]);
        added_bytes += cb[i].value;
      }
    }
    for (ptrdiff_t i = 0; i < ax_hmlen(ca); i++) {
      if (ax_hmgeti(cb, ca[i].key) < 0) {
        removed++;
        removed_bytes += ca[i].value;
      }
    }
    char abytes[32], rbytes[32];
    fmt_bytes(added_bytes, abytes, sizeof(abytes));
    fmt_bytes(removed_bytes, rbytes, sizeof(rbytes));
    printf("%s -> %s: +%td pins (%s), -%zu pins (%s)\n", a, b, ax_arrlen(added),
           abytes, removed, rbytes);
    if (ax_arrlen(added) > 0) {
      printf("  added, largest first:\n");
      print_top_objects(added, (size_t)ax_arrlen(added), 20);
    }
    ax_arrfree(added);
  }
  ax_hmfree(ca);
  ax_hmfree(cb);
}

static void collect_object(void* ctx, const uint8_t hash[32], uint64_t off,
                           uint64_t len) {
  scry_object** objects = ctx;
  scry_object o = {.off = off, .len = len};
  memcpy(o.hash.b, hash, 32);
  ax_arrpush(*objects, o);
}

static int object_off_asc(const void* a, const void* b) {
  const scry_object* x = a;
  const scry_object* y = b;
  if (x->off != y->off)
    return x->off < y->off ? -1 : 1;
  return 0;
}

/* Bucket every indexed object between the journal's pack-size
 * watermarks: "what did save N append". */
static void cmd_packmap(scry* sc, const char* arg) {
  uint64_t top = 5;
  if (arg != NULL && !parse_u64(arg, &top)) {
    fprintf(stderr, "scry: packmap takes a per-snapshot object count\n");
    return;
  }
  size_t nlog = 0;
  pl_store_root_entry* entries = journal_fetch(sc->store, &nlog);
  scry_object* objects = NULL;
  (void)pl_store_silo_objects(sc->store, collect_object, &objects);
  size_t nobj = (size_t)ax_arrlen(objects);
  qsort(objects, nobj, sizeof(*objects), object_off_asc);

  size_t oi = 0;
  for (size_t e = 0; e <= nlog; e++) {
    bool tail = e == nlog;
    uint64_t hi = tail ? UINT64_MAX : entries[e].pack_bytes;
    closure_entry* bucket = NULL;
    uint64_t bucket_bytes = 0;
    while (oi < nobj && objects[oi].off < hi) {
      closure_entry ce = {.key = objects[oi].hash, .value = objects[oi].len};
      ax_arrpush(bucket, ce);
      bucket_bytes += objects[oi].len;
      oi++;
    }
    if (ax_arrlen(bucket) == 0) {
      ax_arrfree(bucket);
      continue;
    }
    char size[32];
    fmt_bytes(bucket_bytes, size, sizeof(size));
    if (tail) {
      printf("after last journaled save: %td objects, %s\n", ax_arrlen(bucket),
             size);
    } else {
      char when[32];
      fmt_time(entries[e].unix_ns, when, sizeof(when));
      printf("seq %llu (%s): %td objects, %s\n",
             (unsigned long long)entries[e].seq, when, ax_arrlen(bucket), size);
    }
    print_top_objects(bucket, (size_t)ax_arrlen(bucket), (size_t)top);
    ax_arrfree(bucket);
  }
  if (nlog == 0 && nobj > 0)
    printf("(no journal: %zu objects total, unattributed)\n", nobj);
  ax_arrfree(objects);
  free(entries);
}

/* Representation diagnostics for the cursor value: tag, header, limb
 * count, byte length, and the low bytes — for debugging renderer or
 * decoder anomalies without trusting either. */
static void cmd_raw(scry* sc) {
  if (!need_checkout(sc))
    return;
  pl_val v = sc->path[sc->path_n - 1];
  printf("val=%016llx tag=%llu is_nat63=%d is_nat=%d\n", (unsigned long long)v,
         (unsigned long long)pl_tag(v), pl_is_nat63(v), pl_is_nat(v));
  if (pl_is_nat63(v)) {
    printf("nat63=%llu\n", (unsigned long long)v);
    return;
  }
  pl_cell* p = pl_ptr(v);
  printf("hdr=%016llx kind=%u\n", (unsigned long long)p[0],
         (unsigned)pl_hdr_kind(p[0]));
  if (pl_is_nat(v)) {
    size_t limbs = pl_nat_limb_len(v);
    size_t bytes = pl_nat_byte_len(v);
    printf("limbs=%zu byte_len=%zu bits=%zu\n", limbs, bytes,
           pl_nat_bit_len(v));
    size_t show = bytes < 48 ? bytes : 48;
    printf("low bytes: ");
    for (size_t i = 0; i < show; i++)
      printf("%02x", pl_nat_byte_at(v, i));
    printf("%s\n", show < bytes ? "…" : "");
    if (limbs > 0)
      printf("top limb: %016llx\n",
             (unsigned long long)pl_nat_limb_at(v, limbs - 1));
  }
  /* Render through pl_show_sb and hexdump the builder's bytes, so the
   * renderer + string builder are inspected without the tty in the way. */
  ax_sb sb;
  ax_sb_init(&sb, ax_allocator_system());
  pl_show_sb(&sb, v);
  size_t n = 0;
  char* text = ax_sb_build(&sb, &n);
  ax_sb_free(&sb);
  printf("render len=%zu hex: ", n);
  for (size_t i = 0; i < n && i < 96; i++)
    printf("%02x", (uint8_t)text[i]);
  printf("%s\n", n > 96 ? "…" : "");
  ax_free(ax_allocator_system(), text);
}

typedef struct where_scan {
  uint8_t hash[32];
  uint64_t off;
  uint64_t len;
  bool found;
} where_scan;

static void where_object(void* ctx, const uint8_t hash[32], uint64_t off,
                         uint64_t len) {
  where_scan* w = ctx;
  if (!w->found && memcmp(hash, w->hash, 32) == 0) {
    w->off = off;
    w->len = len;
    w->found = true;
  }
}

/* Pack placement of one object: "<hash> <offset> <length>" for tools
 * that read pins.pack directly. */
static void cmd_where(scry* sc, const char* arg) {
  if (arg == NULL) {
    fprintf(stderr, "scry: where <seq|hash>\n");
    return;
  }
  where_scan w = {0};
  uint64_t seq;
  if (!resolve_snapshot(sc->store, arg, w.hash, &seq))
    return;
  (void)pl_store_silo_objects(sc->store, where_object, &w);
  if (!w.found) {
    fprintf(stderr, "scry: object is not indexed\n");
    return;
  }
  char hex[65];
  hash_hex(w.hash, 32, hex);
  printf("%s %llu %llu\n", hex, (unsigned long long)w.off,
         (unsigned long long)w.len);
}

static void cmd_help(void) {
  printf("commands:\n"
         "  log [n]            last n journal entries with pack growth\n"
         "  root               current root hash\n"
         "  co [seq|hash]      check out a snapshot (default: current root)\n"
         "  ls                 children of the cursor\n"
         "  cd <i>|..|/        move the cursor\n"
         "  show [depth [w]]   pretty-print the cursor\n"
         "  size [seq|hash]    persisted bytes of a pin closure\n"
         "  diff <a> <b>       pins added/removed between two snapshots\n"
         "  packmap [n]        pack growth bucketed by snapshot\n"
         "  quit\n");
}

/* Returns false when the session should end. */
static bool dispatch(scry* sc, int argc, char** argv) {
  if (argc == 0)
    return true;
  const char* cmd = argv[0];
  const char* a1 = argc > 1 ? argv[1] : NULL;
  const char* a2 = argc > 2 ? argv[2] : NULL;
  if (strcmp(cmd, "log") == 0)
    cmd_log(sc, a1);
  else if (strcmp(cmd, "root") == 0)
    cmd_root(sc);
  else if (strcmp(cmd, "co") == 0)
    cmd_co(sc, a1);
  else if (strcmp(cmd, "ls") == 0)
    cmd_ls(sc);
  else if (strcmp(cmd, "cd") == 0)
    cmd_cd(sc, a1);
  else if (strcmp(cmd, "show") == 0)
    cmd_show(sc, a1, a2);
  else if (strcmp(cmd, "size") == 0)
    cmd_size(sc, a1);
  else if (strcmp(cmd, "diff") == 0)
    cmd_diff(sc, a1, a2);
  else if (strcmp(cmd, "packmap") == 0)
    cmd_packmap(sc, a1);
  else if (strcmp(cmd, "where") == 0)
    cmd_where(sc, a1);
  else if (strcmp(cmd, "raw") == 0)
    cmd_raw(sc);
  else if (strcmp(cmd, "help") == 0)
    cmd_help();
  else if (strcmp(cmd, "quit") == 0 || strcmp(cmd, "exit") == 0)
    return false;
  else
    fprintf(stderr, "scry: unknown command '%s' (try: help)\n", cmd);
  return true;
}

static void repl(scry* sc) {
  char line[1024];
  for (;;) {
    printf("scry");
    if (sc->loaded) {
      if (sc->seq != 0) {
        printf("@%llu", (unsigned long long)sc->seq);
      } else {
        char hex[9];
        hash_hex(sc->root_hash, 4, hex);
        printf("@%s", hex);
      }
    }
    printf("> ");
    fflush(stdout);
    if (fgets(line, sizeof(line), stdin) == NULL)
      break;
    char* argv[8];
    int argc = 0;
    for (char* tok = strtok(line, " \t\r\n");
         tok != NULL && argc < (int)(sizeof(argv) / sizeof(argv[0]));
         tok = strtok(NULL, " \t\r\n"))
      argv[argc++] = tok;
    if (!dispatch(sc, argc, argv))
      break;
  }
}

int main(int argc, char** argv) {
  size_t map_size = SCRY_STORE_MAP_SIZE;
  int at = 1;
  while (at < argc && strncmp(argv[at], "--", 2) == 0) {
    if (strcmp(argv[at], "--map-size") == 0 && at + 1 < argc) {
      uint64_t v;
      if (!parse_u64(argv[at + 1], &v) || v == 0) {
        fprintf(stderr, "scry: bad --map-size\n");
        return 2;
      }
      map_size = (size_t)v;
      at += 2;
    } else {
      fprintf(stderr, "scry: unknown option '%s'\n", argv[at]);
      return 2;
    }
  }
  if (at >= argc) {
    fprintf(stderr,
            "usage: scry [--map-size BYTES] STORE-DIR [COMMAND [ARGS...]]\n");
    return 2;
  }
  const char* dir = argv[at++];

  scry sc = {0};
  sc.store = pl_store_new_silo_ro(dir, map_size);
  if (sc.store == NULL) {
    fprintf(stderr, "scry: cannot open Silo store at %s (read-only)\n", dir);
    return 1;
  }
  sc.heap = pl_heap_new(SCRY_HEAP_CELLS, sc.store);
  sc.thread = pl_thread_new(sc.heap);

  if (at < argc)
    (void)dispatch(&sc, argc - at, argv + at);
  else
    repl(&sc);

  pl_thread_free(sc.thread);
  pl_heap_free(sc.heap);
  pl_store_free(sc.store);
  return 0;
}
