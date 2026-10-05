#include "test.h"
#include "test_plan.h"
#include "../../pkg/plan/src/native_wire.h"
#include <string.h>

static pl_val call_wire(pl_thread* t, bool pack, pl_val seeds, pl_val value) {
  size_t base = t->vsp;
  pl_vpush(t, seeds); pl_vpush(t, value);
  pl_val result = pack ? pl_native_pack(t, base) : pl_native_unpack(t, base);
  t->vsp = base;
  return result;
}
static pl_val payload(pl_val result, bool ok) {
  ASSERT_EQ(pl_tag(result), PL_TAG_APP);
  ASSERT_EQ(pl_app_n(pl_ptr(result)), 1);
  ASSERT_EQ(pl_app_head(pl_ptr(result)), ok ? 0 : 1);
  return pl_app_args(pl_ptr(result))[0];
}

TEST(native_wire, preserves_large_shared_graph) {
  test_rt rt = test_rt_new(); pl_thread* t = rt.t;
  pl_vpush(t, 42);
  for (int i = 0; i < 26; i++) t->vstack[0] = test_app2(t, 0, t->vstack[0], t->vstack[0]);
  pl_vpush(t, payload(call_wire(t, true, 0, t->vstack[0]), true));
  ASSERT_LT(pl_nat_byte_len(t->vstack[1]), 2048);
  pl_val restored = payload(call_wire(t, false, 0, t->vstack[1]), true);
  for (int i = 0; i < 26; i++) {
    ASSERT_EQ(pl_tag(restored), PL_TAG_APP);
    ASSERT_EQ(pl_app_n(pl_ptr(restored)), 2);
    pl_val* args = pl_app_args(pl_ptr(restored));
    ASSERT_EQ(args[0], args[1]);
    restored = args[0];
  }
  ASSERT_EQ(restored, 42);
  t->vsp = 0; test_rt_free(&rt);
}

TEST(native_wire, requires_exact_seed_basis) {
  test_rt rt = test_rt_new(); pl_thread* t = rt.t;
  pl_vpush(t, pl_pin(t, 7));
  pl_vpush(t, test_app1(t, 0, t->vstack[0]));
  pl_vpush(t, payload(call_wire(t, true, t->vstack[1], t->vstack[0]), true));
  pl_val restored = payload(call_wire(t, false, t->vstack[1], t->vstack[2]), true);
  ASSERT_EQ(restored, t->vstack[0]);
  pl_vpush(t, pl_pin(t, 8));
  t->vstack[3] = test_app1(t, 0, t->vstack[3]);
  payload(call_wire(t, false, t->vstack[3], t->vstack[2]), false);
  payload(call_wire(t, false, 0, t->vstack[2]), false);
  t->vsp = 0; test_rt_free(&rt);
}

TEST(native_wire, references_exact_substructure_of_verified_seed) {
  test_rt rt = test_rt_new(); pl_thread* t = rt.t;
  pl_vpush(t, test_app2(t, 0, 41, 42));
  pl_vpush(t, pl_pin(t, t->vstack[0]));
  pl_vpush(t, test_app1(t, 0, t->vstack[1]));
  /* Interning can copy the seed. Use the actual canonical body's reference,
   * as the compiler does with its imported native module image. */
  payload(call_wire(t, true, t->vstack[2], 0), true);
  pl_val body = pl_pin_body(pl_ptr(t->vstack[1]));
  pl_vpush(t, payload(call_wire(t, true, t->vstack[2], body), true));
  ASSERT_EQ(pl_nat_byte_at(t->vstack[3], 41), 5);
  pl_val value = payload(call_wire(t, false, t->vstack[2], t->vstack[3]), true);
  ASSERT_EQ(value, pl_pin_body(pl_ptr(t->vstack[1])));
  uint8_t bytes[64]; size_t n = pl_nat_byte_len(t->vstack[3]);
  ASSERT_LT(n, sizeof(bytes));
  for (size_t i = 0; i < n; i++) bytes[i] = pl_nat_byte_at(t->vstack[3], i);
  /* A PIN has only body selector zero; this must never resolve elsewhere. */
  bytes[50] = 1;
  payload(call_wire(t, false, t->vstack[2], pl_nat_from_bytes(t, bytes, n)), false);
  t->vsp = 0; test_rt_free(&rt);
}

TEST(native_wire, fresh_seed_keeps_original_graph_aliases) {
  test_rt rt = test_rt_new(); pl_thread* t = rt.t;
  pl_vpush(t, 42);
  for (int i = 0; i < 200; i++)
    t->vstack[0] = test_app2(t, 0, (pl_val)i, t->vstack[0]);
  pl_vpush(t, pl_pin(t, t->vstack[0]));
  pl_vpush(t, test_app1(t, 0, t->vstack[1]));
  pl_vpush(t, payload(call_wire(t, true, t->vstack[2], t->vstack[0]), true));
  ASSERT_LT(pl_nat_byte_len(t->vstack[3]), 100);
  pl_val restored = payload(call_wire(t, false, t->vstack[2], t->vstack[3]), true);
  ASSERT_EQ(restored, pl_pin_body(pl_ptr(t->vstack[1])));
  for (int i = 199; i >= 0; i--) {
    ASSERT_EQ(pl_app_args(pl_ptr(restored))[0], (pl_val)i);
    restored = pl_app_args(pl_ptr(restored))[1];
  }
  ASSERT_EQ(restored, 42);
  t->vsp = 0; test_rt_free(&rt);
}

TEST(native_wire, shortest_route_wins_across_shared_seed_ancestors) {
  test_rt rt = test_rt_new(); pl_thread* t = rt.t;
  pl_vpush(t, test_app2(t, 0, 41, 42));
  pl_vpush(t, pl_pin(t, t->vstack[0]));
  pl_vpush(t, t->vstack[1]);
  for (int i = 0; i < 100; i++)
    t->vstack[2] = test_app1(t, 0, t->vstack[2]);
  t->vstack[2] = pl_pin(t, t->vstack[2]);
  pl_vpush(t, test_app2(t, 0, t->vstack[1], t->vstack[2]));
  payload(call_wire(t, true, t->vstack[3], 0), true);
  pl_val body = pl_pin_body(pl_ptr(t->vstack[1]));
  pl_vpush(t, payload(call_wire(t, true, t->vstack[3], body), true));
  ASSERT_LT(pl_nat_byte_len(t->vstack[4]), 100);
  pl_val restored = payload(call_wire(t, false, t->vstack[3], t->vstack[4]), true);
  ASSERT_EQ(restored, pl_pin_body(pl_ptr(t->vstack[1])));
  t->vsp = 0; test_rt_free(&rt);
}

TEST(native_wire, rejects_redex_and_malformed_values) {
  static const uint8_t redex[] = {'S','R','N','V','3',3,1,0,0,0,2,0,1,0,0,0,82,0,0,0,0,0,1};
  static const uint8_t ref[] = {'S','R','N','V','3',4,255,255,255,255,1};
  static const uint8_t nat[] = {'S','R','N','V','3',0,255,255,255,255,1};
  static const uint8_t zero[] = {'S','R','N','V','3',0,1,0,0,0,0,1};
  static const uint8_t row[] = {'S','R','N','V','3',3,255,255,255,255,1};
  const uint8_t* bad[] = {redex,ref,nat,zero,row};
  size_t lengths[] = {sizeof(redex),sizeof(ref),sizeof(nat),sizeof(zero),sizeof(row)};
  test_rt rt = test_rt_new();
  for (size_t i = 0; i < 5; i++)
    payload(call_wire(rt.t, false, 0, pl_nat_from_bytes(rt.t, bad[i], lengths[i])), false);
  test_rt_free(&rt);
}

TEST(native_wire, truncations_and_byte_mutations_stay_bounded) {
  test_rt rt = test_rt_new(); pl_thread* t = rt.t;
  pl_vpush(t, test_law(t, 2, 0, 1));
  pl_vpush(t, test_app1(t, t->vstack[0], 41));
  pl_vpush(t, payload(call_wire(t, true, 0, t->vstack[1]), true));
  uint8_t bytes[256]; size_t n = pl_nat_byte_len(t->vstack[2]);
  ASSERT_LT(n, sizeof(bytes));
  for (size_t i = 0; i < n; i++) bytes[i] = pl_nat_byte_at(t->vstack[2], i);
  for (size_t i = 0; i + 1 < n; i++) {
    uint8_t saved = bytes[i]; bytes[i] = 1;
    payload(call_wire(t, false, 0, pl_nat_from_bytes(t, bytes, i + 1)), false);
    bytes[i] = saved;
  }
  for (size_t i = 5; i + 1 < n; i++) {
    uint8_t saved = bytes[i];
    for (unsigned m = 0; m < 256; m += 17) {
      bytes[i] = (uint8_t)m;
      pl_val result = call_wire(t, false, 0, pl_nat_from_bytes(t, bytes, n));
      ASSERT_EQ(pl_tag(result), PL_TAG_APP);
      ASSERT_LTE(pl_app_head(pl_ptr(result)), 1);
      if (pl_app_head(pl_ptr(result)) == 0) {
        pl_val encoded = payload(call_wire(t, true, 0, payload(result, true)), true);
        payload(call_wire(t, false, 0, encoded), true);
      }
    }
    bytes[i] = saved;
  }
  t->vsp = 0; test_rt_free(&rt);
}
