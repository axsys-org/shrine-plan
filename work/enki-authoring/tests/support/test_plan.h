#pragma once

/* Shared fixture helpers for plan-layer tests. */

#include <setjmp.h>

#include "plan/build.h"
#include "plan/debug.h"
#include "plan/eval.h"
#include "plan/heap.h"
#include "plan/nat.h"
#include "plan/store.h"

typedef struct test_rt {
  pl_store* store;
  pl_heap* heap;
  pl_thread* t;
} test_rt;

static test_rt test_rt_new(void) {
  test_rt rt;
  rt.store = pl_store_new_mem();
  rt.heap = pl_heap_new(1 << 16, rt.store);
  rt.t = pl_thread_new(rt.heap);
  return rt;
}

static void test_rt_free(test_rt* rt) {
  pl_thread_free(rt->t);
  pl_heap_free(rt->heap);
  pl_store_free(rt->store);
}

/* Build an n-ary application with rooted operands. */
static pl_val test_app(pl_thread* t, pl_val head, size_t n,
                       const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, head);
  for (size_t i = 0; i < n; i++)
    pl_vpush(t, args[i]);
  pl_gc_reserve(t, PL_APP_CELLS(n));
  pl_val out =
      pl_mk_app_from(t, t->vstack[base], (uint32_t)n, &t->vstack[base + 1]);
  t->vsp = base;
  return out;
}

static pl_val test_app2(pl_thread* t, pl_val h, pl_val a, pl_val b) {
  pl_val args[2] = {a, b};
  return test_app(t, h, 2, args);
}

static pl_val test_app1(pl_thread* t, pl_val h, pl_val a) {
  pl_val args[1] = {a};
  return test_app(t, h, 1, args);
}

static pl_val test_law(pl_thread* t, uint64_t arity, pl_val name, pl_val body) {
  size_t base = t->vsp;
  pl_vpush(t, name);
  pl_vpush(t, body);
  pl_gc_reserve(t, PL_LAW_CELLS);
  pl_val out = pl_mk_law(t, arity, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  return out;
}

/* The pin of nat 66, the extended-op set. */
static pl_val test_p66(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 66);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

/* op66 invocation: P66 % (name a...) */
static pl_val test_op66(pl_thread* t, pl_val name, size_t n,
                        const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, test_app(t, name, n, args));
  pl_vpush(t, test_p66(t));
  pl_val row = t->vstack[base];
  pl_val p66 = t->vstack[base + 1];
  t->vsp = base;
  return pl_apply(t, p66, row);
}

static pl_val test_op66_2(pl_thread* t, pl_val name, pl_val a, pl_val b) {
  pl_val args[2] = {a, b};
  return test_op66(t, name, 2, args);
}
