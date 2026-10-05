#include "test.h"
#include <string.h>

#include "axsys/allocator.h"
#include "plan/canon.h"
#include "test_plan.h"

/*
 * Canonical-text rendering, checked against hand-derived reference
 * (Print.hs) output.  These bytes are normative for legacy stores and text
 * snapshots; Silo stores use canonical Silo bytes for identity.
 */

static char* show(pl_thread* t, pl_val v) {
  v = pl_nf(t, v);
  return pl_show_val(ax_allocator_system(), v, NULL);
}

TEST(canon, nat_and_string) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  char* a = show(t, 42);
  ASSERT_STR_EQ(a, "42");
  ax_free(ax_allocator_system(), a);

  /* "foo" little-endian = 'f' | 'o'<<8 | 'o'<<16 */
  pl_val foo = (pl_val)'f' | ((pl_val)'o' << 8) | ((pl_val)'o' << 16);
  char* b = show(t, foo);
  ASSERT_STR_EQ(b, "\"foo\"");
  ax_free(ax_allocator_system(), b);

  /* a single non-alpha byte is a number, not a string */
  char* c = show(t, (pl_val)'0');
  ASSERT_STR_EQ(c, "48");
  ax_free(ax_allocator_system(), c);

  test_rt_free(&rt);
}

TEST(canon, application_row) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 1, 2)); /* (0 1 2) */
  char* s = show(t, t->vstack[base]);
  ASSERT_STR_EQ(s, "(0 1 2)");
  ax_free(ax_allocator_system(), s);
  test_rt_free(&rt);
}

TEST(canon, law_self_and_vars) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* L 2 "f" (0 1 2): a 2-ary law tagged "f", body applies arg1 to arg2.
   * extract: self<-"f", args 1,2 -> a,b; body (var1 var2) -> (a b). */
  pl_vpush(t, test_law(t, 2, (pl_val)'f', test_app2(t, 0, 1, 2)));
  char* s = show(t, t->vstack[base]);
  ASSERT_STR_EQ(s, "(#law \"f\" (f a b) (a b))");
  ax_free(ax_allocator_system(), s);
  test_rt_free(&rt);
}

TEST(canon, law_with_let) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* L 1 "g" (1 7 2): one let binding = 7, body = var2 (the let var).
   * self<-"g", arg1<-a, let var2<-b; the rhs is a raw nat 7, which
   * extractExpr renders as an escaped literal #(7) (then wrap parens). */
  pl_vpush(t, test_law(t, 1, (pl_val)'g', test_app2(t, 1, 7, 2)));
  char* s = show(t, t->vstack[base]);
  ASSERT_STR_EQ(s, "(#law \"g\" (g a) b(#(7)) b)");
  ax_free(ax_allocator_system(), s);
  test_rt_free(&rt);
}

TEST(canon, pin_of_nat) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, 42);
  pl_val pin = pl_pin(t, t->vstack[base]);
  char* s = pl_show_val(ax_allocator_system(), pin, NULL);
  ASSERT_STR_EQ(s, "liquid");
  ax_free(ax_allocator_system(), s);
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, pin, NULL, err, sizeof(err)), "%s", err);
  s = pl_show_val(ax_allocator_system(), pin, NULL);
  ASSERT_STR_EQ(s, "(#pin 42)");
  ax_free(ax_allocator_system(), s);
  test_rt_free(&rt);
}

TEST(canon, canonize_module_text) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* pin a law with no sub-pins: the snapshot has no imports. */
  pl_vpush(t, test_law(t, 1, (pl_val)'h', test_app2(t, 0, 1, 1)));
  pl_val pin = pl_pin(t, t->vstack[base]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, pin, NULL, err, sizeof(err)), "%s", err);
  char* s = pl_canonize(ax_allocator_system(), pin, NULL);
  ASSERT_STR_EQ(s, "(#bind _ (#pin (#law \"h\" (h a) (a a))))\n(#export _)\n");
  ax_free(ax_allocator_system(), s);
  test_rt_free(&rt);
}

TEST(canon, saved_pin_hash_is_canonical_text) {
  /* Save hashes legacy PINs from canonical text and aliases structurally equal
   * proxies to the same canonical store representative. */
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, (pl_val)'h', test_app2(t, 0, 1, 1)));
  pl_vpush(t, test_law(t, 1, (pl_val)'h', test_app2(t, 0, 1, 1)));
  /* Public PINs move with the heap until Save resolves them.  Keep the first
   * proxy rooted while constructing the second, especially in GC_STRESS. */
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val p1 = t->vstack[base];
  pl_val p2 = t->vstack[base + 1];
  ASSERT_NEQ(p1, p2);
  ASSERT_NULL(pl_pin_hash(p1));
  ASSERT_NULL(pl_pin_hash(p2));
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, p1, NULL, err, sizeof(err)), "%s", err);
  ASSERT(pl_store_save_root(rt.store, p2, NULL, err, sizeof(err)), "%s", err);
  ASSERT_EQ(memcmp(pl_pin_hash(p1), pl_pin_hash(p2), 32), 0);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(p1)), pl_pin_proxy_target(pl_ptr(p2)));
  test_rt_free(&rt);
}
