#include "plan/nat.h"

#include <gmp.h>
#include <string.h>

#include "axsys/assume.h"
#include "plan/build.h"
#include "plan/eval.h"

static_assert(sizeof(mp_limb_t) == sizeof(uint64_t),
              "mpn limbs must be 64-bit");

/*
 * The heap stores limbs as uint64_t cells.  On LP64 glibc that is the
 * same type as mp_limb_t (unsigned long); on Darwin uint64_t is
 * unsigned long long, a distinct pointer type of identical layout
 * (asserted above), so mpn destinations need an explicit cast.
 */
static mp_limb_t* mpn_dst(uint64_t* p) {
  return (mp_limb_t*)p;
}

/*
 * Limb view of a nat.  For a direct nat the limb is copied into *tmp;
 * for a boxed nat the pointer aliases the heap object, so the view is
 * valid only while nothing moves (use inside a no-collect window, or
 * before any reserve).
 */
typedef struct pl_limbs {
  const mp_limb_t* p;
  size_t n; /* trimmed length; 0 means the value is zero */
} pl_limbs;

static pl_limbs pl_limb_view(const pl_val* v, mp_limb_t* tmp) {
  if (pl_is_nat63(*v)) {
    *tmp = *v;
    return (pl_limbs){tmp, *v == 0 ? 0 : 1};
  }
  pl_cell* p = pl_ptr(*v);
  ax_assume(pl_hdr_kind(p[0]) == PL_K_NAT, "limb view of non-nat");
  return (pl_limbs){(const mp_limb_t*)pl_nat_limb_ptr(p), pl_nat_limbs(p)};
}

size_t pl_nat_limb_len(pl_val v) {
  mp_limb_t tmp;
  return pl_limb_view(&v, &tmp).n;
}

uint64_t pl_nat_limb_at(pl_val v, size_t i) {
  if (pl_is_nat63(v))
    return i == 0 ? v : 0;
  pl_cell* p = pl_ptr(v);
  return i < pl_nat_limbs(p) ? pl_nat_limb_ptr(p)[i] : 0;
}

int pl_nat_cmp(pl_val a, pl_val b) {
  /* Direct nats are never indirections: compare them in registers before
   * building limb views.  Every Eq/Ne/Lt/Le/Gt/Ge/Cmp body lands here. */
  if (pl_is_nat63(a) && pl_is_nat63(b))
    return a < b ? -1 : (a > b ? 1 : 0);
  mp_limb_t ta, tb;
  pl_val va = pl_resolve(a);
  pl_val vb = pl_resolve(b);
  if (va == vb) {
    return 0;
  }
  pl_limbs la = pl_limb_view(&va, &ta);
  pl_limbs lb = pl_limb_view(&vb, &tb);

  if (la.n != lb.n)
    return la.n < lb.n ? -1 : 1;
  if (la.n == 0)
    return 0;
  return mpn_cmp(la.p, lb.p, la.n);
}

bool pl_nat_eq(pl_val a, pl_val b) {
  return pl_nat_cmp(a, b) == 0;
}

bool pl_nat_is_zero(pl_val v) {
  return v == 0;
}

uint64_t pl_nat_u64_clamp(pl_val v) {
  if (pl_is_nat63(v))
    return v;
  pl_cell* p = pl_ptr(v);
  uint32_t n = pl_nat_limbs(p);
  if (n == 0)
    return 0;
  if (n == 1)
    return pl_nat_limb_ptr(p)[0];
  return UINT64_MAX;
}

size_t pl_nat_bit_len(pl_val v) {
  mp_limb_t tmp;
  pl_limbs l = pl_limb_view(&v, &tmp);
  if (l.n == 0)
    return 0;
  uint64_t top = l.p[l.n - 1];
  return (l.n - 1) * 64 + (64 - (size_t)__builtin_clzll(top));
}

size_t pl_nat_byte_len(pl_val v) {
  return (pl_nat_bit_len(v) + 7) / 8;
}

uint8_t pl_nat_byte_at(pl_val v, size_t i) {
  uint64_t limb = pl_nat_limb_at(v, i / 8);
  return (uint8_t)(limb >> ((i % 8) * 8));
}

bool pl_nat_test_bit(pl_val bit, pl_val a) {
  uint64_t i = pl_nat_u64_clamp(bit);
  if (i / 64 >= pl_nat_limb_len(a))
    return false;
  return (pl_nat_limb_at(a, i / 64) >> (i % 64)) & 1u;
}

/* ── Allocation helper: build a nat from a scratch result ──────────────── */

/*
 * Result protocol used below: compute the maximum result width from
 * operand sizes only, reserve, re-fetch operands through their rooted
 * slots, open a no-collect window, bump the result object, run mpn into
 * it, trim, close the window.
 */

pl_val pl_nat_inc(pl_thread* t, pl_val* a) {
  if (pl_is_nat63(*a) && *a < PL_NAT63_MAX)
    return *a + 1;
  size_t la = pl_nat_limb_len(*a);
  pl_gc_reserve(t, PL_NAT_CELLS(la + 1));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, la + 1, &out);
  mp_limb_t tmp;
  pl_limbs va = pl_limb_view(a, &tmp);
  out[la] = mpn_add_1(mpn_dst(out), va.p, la, 1);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_dec(pl_thread* t, pl_val* a) {
  if (pl_is_nat63(*a))
    return *a == 0 ? 0 : *a - 1;
  size_t la = pl_nat_limb_len(*a);
  pl_gc_reserve(t, PL_NAT_CELLS(la));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, la, &out);
  mp_limb_t tmp;
  pl_limbs va = pl_limb_view(a, &tmp);
  mpn_sub_1(mpn_dst(out), va.p, la, 1);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_add(pl_thread* t, pl_val* a, pl_val* b) {
  if (pl_is_nat63(*a) && pl_is_nat63(*b)) {
    uint64_t s;
    if (!__builtin_add_overflow(*a, *b, &s) && s <= PL_NAT63_MAX)
      return s;
  }
  size_t la = pl_nat_limb_len(*a), lb = pl_nat_limb_len(*b);
  size_t lr = (la > lb ? la : lb) + 1;
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta, tb;
  pl_limbs va = pl_limb_view(a, &ta), vb = pl_limb_view(b, &tb);
  if (va.n < vb.n) {
    pl_limbs sw = va;
    va = vb;
    vb = sw;
  }
  mp_limb_t carry = vb.n ? mpn_add(mpn_dst(out), va.p, va.n, vb.p, vb.n)
                         : (memcpy(out, va.p, va.n * 8), 0);
  out[va.n] = carry;
  for (size_t i = va.n + 1; i < lr; i++)
    out[i] = 0;
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_sub(pl_thread* t, pl_val* a, pl_val* b) {
  if (pl_is_nat63(*a) && pl_is_nat63(*b))
    return *a > *b ? *a - *b : 0;
  if (pl_nat_cmp(*b, *a) >= 0)
    return 0;
  size_t la = pl_nat_limb_len(*a);
  pl_gc_reserve(t, PL_NAT_CELLS(la));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, la, &out);
  mp_limb_t ta, tb;
  pl_limbs va = pl_limb_view(a, &ta), vb = pl_limb_view(b, &tb);
  mpn_sub(mpn_dst(out), va.p, va.n, vb.p, vb.n);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_mul(pl_thread* t, pl_val* a, pl_val* b) {
  if (pl_is_nat63(*a) && pl_is_nat63(*b)) {
    uint64_t p;
    if (!__builtin_mul_overflow(*a, *b, &p) && p <= PL_NAT63_MAX)
      return p;
  }
  if (*a == 0 || *b == 0)
    return 0;
  size_t la = pl_nat_limb_len(*a), lb = pl_nat_limb_len(*b);
  size_t lr = la + lb;
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta, tb;
  pl_limbs va = pl_limb_view(a, &ta), vb = pl_limb_view(b, &tb);
  if (va.n >= vb.n)
    mpn_mul(mpn_dst(out), va.p, va.n, vb.p, vb.n);
  else
    mpn_mul(mpn_dst(out), vb.p, vb.n, va.p, va.n);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

/*
 * mpn_tdiv_qr requires the divisor's top limb to be nonzero and the
 * quotient/remainder buffers not to alias the operands, so we route
 * through scratch copies sized from the operands.
 */
static pl_val pl_nat_divmod(pl_thread* t, pl_val* a, pl_val* b, bool want_mod) {
  if (*b == 0)
    pl_raise_msg(t, "division by zero");
  if (pl_is_nat63(*a) && pl_is_nat63(*b))
    return want_mod ? *a % *b : *a / *b;
  if (pl_nat_cmp(*a, *b) < 0)
    return want_mod ? *a : 0;
  size_t la = pl_nat_limb_len(*a), lb = pl_nat_limb_len(*b);
  size_t lq = la - lb + 1;
  /* one window: quotient nat + remainder nat + dividend/divisor scratch */
  pl_gc_reserve(t, PL_NAT_CELLS(lq) + PL_NAT_CELLS(lb));
  PL_GC_FORBID(t);
  uint64_t* qp;
  uint64_t* rp;
  pl_val q = pl_mk_nat_limbs(t, lq, &qp);
  pl_val r = pl_mk_nat_limbs(t, lb, &rp);
  mp_limb_t ta, tb;
  pl_limbs va = pl_limb_view(a, &ta), vb = pl_limb_view(b, &tb);
  mpn_tdiv_qr(mpn_dst(qp), mpn_dst(rp), 0, va.p, va.n, vb.p, vb.n);
  q = pl_nat_trim(q);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return want_mod ? r : q;
}

pl_val pl_nat_div(pl_thread* t, pl_val* a, pl_val* b) {
  return pl_nat_divmod(t, a, b, false);
}

pl_val pl_nat_mod(pl_thread* t, pl_val* a, pl_val* b) {
  return pl_nat_divmod(t, a, b, true);
}

pl_val pl_nat_lsh(pl_thread* t, pl_val* a, pl_val* sh) {
  if (*a == 0)
    return 0;
  uint64_t cnt = pl_nat_u64_clamp(*sh);
  size_t la = pl_nat_limb_len(*a);
  size_t limb_shift = cnt / 64, bit_shift = cnt % 64;
  size_t lr = la + limb_shift + 1;
  ax_assume(lr < (1u << 20), "left shift result too large");
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  memset(out, 0, limb_shift * 8);
  if (bit_shift == 0) {
    memcpy(out + limb_shift, va.p, va.n * 8);
    out[limb_shift + va.n] = 0;
  } else {
    out[limb_shift + va.n] =
        mpn_lshift(mpn_dst(out + limb_shift), va.p, va.n, (unsigned)bit_shift);
  }
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_rsh(pl_thread* t, pl_val* a, pl_val* sh) {
  uint64_t cnt = pl_nat_u64_clamp(*sh);
  size_t la = pl_nat_limb_len(*a);
  size_t limb_shift = cnt / 64, bit_shift = cnt % 64;
  if (limb_shift >= la)
    return 0;
  size_t lr = la - limb_shift;
  if (pl_is_nat63(*a))
    return *a >> cnt;
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  if (bit_shift == 0)
    memcpy(out, va.p + limb_shift, lr * 8);
  else
    mpn_rshift(mpn_dst(out), va.p + limb_shift, lr, (unsigned)bit_shift);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_bex(pl_thread* t, pl_val* bits) {
  uint64_t n = pl_nat_u64_clamp(*bits);
  if (n < 63)
    return UINT64_C(1) << n;
  size_t lr = n / 64 + 1;
  ax_assume(lr < (1u << 20), "bex result too large");
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  memset(out, 0, lr * 8);
  out[n / 64] = UINT64_C(1) << (n % 64);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_set_bit(pl_thread* t, pl_val* bit, pl_val* a) {
  uint64_t i = pl_nat_u64_clamp(*bit);
  if (pl_is_nat63(*a) && i < 63)
    return *a | (UINT64_C(1) << i);
  size_t la = pl_nat_limb_len(*a);
  size_t lr = (i / 64 + 1 > la) ? i / 64 + 1 : la;
  ax_assume(lr < (1u << 20), "set-bit result too large");
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  memset(out, 0, lr * 8);
  memcpy(out, va.p, va.n * 8);
  out[i / 64] |= UINT64_C(1) << (i % 64);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_clear_bit(pl_thread* t, pl_val* bit, pl_val* a) {
  uint64_t i = pl_nat_u64_clamp(*bit);
  if (pl_is_nat63(*a))
    return i < 63 ? (*a & ~(UINT64_C(1) << i)) : *a;
  size_t la = pl_nat_limb_len(*a);
  if (i / 64 >= la)
    return *a;
  pl_gc_reserve(t, PL_NAT_CELLS(la));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, la, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  memcpy(out, va.p, va.n * 8);
  out[i / 64] &= ~(UINT64_C(1) << (i % 64));
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_trunc(pl_thread* t, pl_val* width, pl_val* a) {
  uint64_t w = pl_nat_u64_clamp(*width);
  if (w == 0)
    return 0;
  if (pl_nat_bit_len(*a) <= w)
    return *a;
  if (pl_is_nat63(*a))
    return w >= 63 ? *a : (*a & ((UINT64_C(1) << w) - 1));
  size_t lr = (w + 63) / 64;
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  memcpy(out, va.p, lr * 8);
  if (w % 64 != 0)
    out[lr - 1] &= (UINT64_C(1) << (w % 64)) - 1;
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

static uint64_t clamp_to_width(uint64_t w, uint64_t a) {
  if (w >= 8)
    return a;
  return a & ((UINT64_C(1) << (w * 8)) - 1);
}

/* LoadVar: (a >> 8*off) mod 2^(8*width); bytes past the end read as zero */
pl_val pl_nat_load_var(pl_thread* t, pl_val* off, pl_val* width, pl_val* a) {
  uint64_t w = pl_nat_u64_clamp(*width);
  uint64_t o = pl_nat_u64_clamp(*off);
  if (w == 0)
    return 0;
  if (pl_is_nat63(*a))
    return o >= 8 ? 0 : clamp_to_width(w, (*a) >> (8 * o));
  size_t avail = pl_nat_limb_len(*a) * 8;
  if (o >= avail)
    return 0;
  size_t n = (avail - o < w) ? avail - o : (size_t)w;
  size_t lr = (n + 7) / 8;
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  out[lr - 1] = 0;
  memcpy(out, (const char*)va.p + o, n);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

/* writeByte from the reference: replace byte i of n with b. */
pl_val pl_nat_store_byte(pl_thread* t, pl_val* idx, pl_val* byte, pl_val* a) {
  uint64_t i = pl_nat_u64_clamp(*idx);
  uint8_t b = (uint8_t)pl_nat_u64_clamp(pl_nat_coerce(*byte));
  size_t la = pl_nat_limb_len(*a);
  size_t lr = i / 8 + 1; /* limb holding byte i */
  if (lr < la)
    lr = la;
  ax_assume(lr < (1u << 20), "store-byte result too large");
  pl_gc_reserve(t, PL_NAT_CELLS(lr));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, lr, &out);
  mp_limb_t ta;
  pl_limbs va = pl_limb_view(a, &ta);
  memset(out, 0, lr * 8);
  memcpy(out, va.p, va.n * 8);
  ((uint8_t*)out)[i] = b;
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

/* ── Construction ──────────────────────────────────────────────────────── */

pl_val pl_nat_from_bytes(pl_thread* t, const uint8_t* b, size_t n) {
  while (n > 0 && b[n - 1] == 0)
    n--;
  if (n == 0)
    return 0;
  if (n < 8) {
    uint64_t v = 0;
    memcpy(&v, b, n); /* little-endian hosts only (asserted in assume.h) */
    return v;
  }
  size_t limbs = (n + 7) / 8;
  pl_gc_reserve(t, PL_NAT_CELLS(limbs));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val r = pl_mk_nat_limbs(t, limbs, &out);
  out[limbs - 1] = 0;
  memcpy(out, b, n);
  r = pl_nat_trim(r);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_nat_from_decimal(pl_thread* t, const char* s, size_t n, bool* ok) {
  char* buf = malloc(n + 1);
  ax_assume(buf != NULL, "oom");
  memcpy(buf, s, n);
  buf[n] = '\0';
  mpz_t z;
  mpz_init(z);
  if (mpz_set_str(z, buf, 10) != 0 || mpz_sgn(z) < 0) {
    mpz_clear(z);
    free(buf);
    *ok = false;
    return 0;
  }
  free(buf);
  size_t limbs = mpz_size(z);
  pl_val r;
  if (limbs == 0) {
    r = 0;
  } else {
    pl_gc_reserve(t, PL_NAT_CELLS(limbs));
    PL_GC_FORBID(t);
    uint64_t* out;
    r = pl_mk_nat_limbs(t, limbs, &out);
    memset(out, 0, limbs * 8);
    size_t written = 0;
    mpz_export(out, &written, -1, sizeof(uint64_t), 0, 0, z);
    r = pl_nat_trim(r);
    PL_GC_ALLOW(t);
  }
  mpz_clear(z);
  *ok = true;
  return r;
}
