#include "plan/debug.h"

#include <ctype.h>
#include <gmp.h>
#include <string.h>

#include "axsys/sb.h"
#include "plan/nat.h"
#include "plan/store.h"
#include "plan/value.h"

static void pl_gmp_free(void* ptr, size_t size_s) {
  if (ptr == NULL)
    return;
  void (*free_fn)(void*, size_t) = NULL;
  mp_get_memory_functions(NULL, NULL, &free_fn);
  free_fn(ptr, size_s);
}

static bool pl_nat_printable(pl_val v) {
  size_t n = pl_nat_byte_len(v);
  if (n == 0 || (pl_is_nat63(v) && v < 256))
    return false;
  for (size_t i = 0; i < n; i++) {
    if (!isprint(pl_nat_byte_at(v, i)))
      return false;
  }
  return true;
}

static void pl_show_nat(ax_sb* sb, pl_val v) {
  if (pl_nat_printable(v)) {
    ax_sb_append_lit(sb, "\"");
    size_t n = pl_nat_byte_len(v);
    for (size_t i = 0; i < n; i++)
      ax_sb_append_char(sb, (char)pl_nat_byte_at(v, i));
    ax_sb_append_lit(sb, "\"");
    return;
  }
  if (pl_is_nat63(v)) {
    ax_sb_append_u64(sb, v);
    return;
  }
  mpz_t z;
  mpz_init(z);
  size_t limbs = pl_nat_limb_len(v);
  mpz_import(z, limbs, -1, sizeof(uint64_t), 0, 0, pl_nat_limb_ptr(pl_ptr(v)));
  char* dec = mpz_get_str(NULL, 10, z);
  /* ax_sb defers: appended strings are referenced until materialization,
   * so the digits must be copied in — appending dec and then freeing it
   * reads freed memory at build time. */
  for (const char* q = dec; *q != '\0'; q++)
    ax_sb_append_char(sb, *q);
  pl_gmp_free(dec, strlen(dec) + 1);
  mpz_clear(z);
}

static bool pl_show_name_raw(ax_sb* sb, pl_val name) {
  if (!pl_is_nat(name) || !pl_nat_printable(name))
    return false;
  size_t n = pl_nat_byte_len(name);
  for (size_t i = 0; i < n; i++)
    ax_sb_append_char(sb, (char)pl_nat_byte_at(name, i));
  return true;
}

void pl_show_sb(ax_sb* sb, pl_val v) {
  while (!pl_is_nat63(v) && pl_tag(v) == PL_TAG_DEFER &&
         pl_hdr_kind(*pl_ptr(v)) == PL_K_IND)
    v = pl_ind_target(pl_ptr(v));

  if (pl_is_nat(v)) {
    pl_show_nat(sb, v);
    return;
  }
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_APP: {
    ax_sb_append_lit(sb, "(");
    pl_show_sb(sb, pl_app_head(p));
    uint32_t n = pl_app_n(p);
    for (uint32_t i = 0; i < n; i++) {
      ax_sb_append_lit(sb, " ");
      pl_show_sb(sb, pl_app_args(p)[i]);
    }
    ax_sb_append_lit(sb, ")");
    return;
  }
  case PL_TAG_LAW: {
    ax_sb_append_lit(sb, "{");
    if (!pl_show_name_raw(sb, pl_law_name(p)))
      pl_show_sb(sb, pl_law_name(p));
    ax_sb_append_lit(sb, "/");
    ax_sb_append_u64(sb, pl_law_arity(p));
    ax_sb_append_lit(sb, " ");
    pl_show_sb(sb, pl_law_body(p));
    ax_sb_append_lit(sb, "}");
    return;
  }
  case PL_TAG_PIN:
    ax_sb_append_lit(sb, "<");
    pl_show_sb(sb, pl_pin_body(p));
    ax_sb_append_lit(sb, ">");
    return;
  case PL_TAG_ENV:
    ax_sb_append_lit(sb, "<env/");
    ax_sb_append_u64(sb, pl_env_n(p));
    ax_sb_append_lit(sb, ">");
    return;
  case PL_TAG_DEFER:
    if (pl_hdr_kind(p[0]) == PL_K_BH)
      ax_sb_append_lit(sb, "<bh>");
    else
      ax_sb_append_lit(sb, "<thk>");
    return;
  default:
    ax_sb_append_lit(sb, "<<bad>>");
    return;
  }
}

#define PL_SHOW_NAT_MAX_BYTES 64u

static void pl_show_limited_rec(ax_sb* sb, pl_val v, size_t depth,
                                size_t max_width) {
  while (!pl_is_nat63(v) && pl_tag(v) == PL_TAG_DEFER &&
         pl_hdr_kind(*pl_ptr(v)) == PL_K_IND)
    v = pl_ind_target(pl_ptr(v));

  if (pl_is_nat(v)) {
    if (pl_nat_byte_len(v) > PL_SHOW_NAT_MAX_BYTES) {
      ax_sb_append_lit(sb, "<nat:");
      ax_sb_append_u64(sb, pl_nat_byte_len(v));
      ax_sb_append_lit(sb, " bytes>");
    } else {
      pl_show_nat(sb, v);
    }
    return;
  }
  if (depth == 0) {
    ax_sb_append_lit(sb, "…");
    return;
  }
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_APP: {
    ax_sb_append_lit(sb, "(");
    pl_show_limited_rec(sb, pl_app_head(p), depth - 1, max_width);
    uint32_t n = pl_app_n(p);
    uint32_t shown = n < max_width ? n : (uint32_t)max_width;
    for (uint32_t i = 0; i < shown; i++) {
      ax_sb_append_lit(sb, " ");
      pl_show_limited_rec(sb, pl_app_args(p)[i], depth - 1, max_width);
    }
    if (shown < n) {
      ax_sb_append_lit(sb, " …+");
      ax_sb_append_u64(sb, n - shown);
    }
    ax_sb_append_lit(sb, ")");
    return;
  }
  case PL_TAG_LAW: {
    ax_sb_append_lit(sb, "{");
    if (!pl_show_name_raw(sb, pl_law_name(p)))
      pl_show_limited_rec(sb, pl_law_name(p), depth - 1, max_width);
    ax_sb_append_lit(sb, "/");
    ax_sb_append_u64(sb, pl_law_arity(p));
    ax_sb_append_lit(sb, " ");
    pl_show_limited_rec(sb, pl_law_body(p), depth - 1, max_width);
    ax_sb_append_lit(sb, "}");
    return;
  }
  case PL_TAG_PIN: {
    const uint8_t* hash = pl_pin_hash(v);
    if (hash != NULL) {
      ax_sb_append_lit(sb, "<pin ");
      for (size_t i = 0; i < 4; i++) {
        static const char hex[] = "0123456789abcdef";
        ax_sb_append_char(sb, hex[hash[i] >> 4]);
        ax_sb_append_char(sb, hex[hash[i] & 0xf]);
      }
      ax_sb_append_lit(sb, ">");
      return;
    }
    ax_sb_append_lit(sb, "<");
    pl_show_limited_rec(sb, pl_pin_body(p), depth - 1, max_width);
    ax_sb_append_lit(sb, ">");
    return;
  }
  default:
    pl_show_sb(sb, v);
    return;
  }
}

void pl_show_limited_sb(ax_sb* sb, pl_val v, size_t max_depth,
                        size_t max_width) {
  pl_show_limited_rec(sb, v, max_depth, max_width);
}

char* pl_show(const ax_allocator* a, pl_val v, size_t* out_s) {
  ax_sb sb;
  ax_sb_init(&sb, a);
  pl_show_sb(&sb, v);
  char* out = ax_sb_build(&sb, out_s);
  ax_sb_free(&sb);
  return out;
}
