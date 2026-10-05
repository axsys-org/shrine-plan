#include <stdbool.h>
#include <stdio.h>

#include "enki/actor.h"
#include "test.h"
#include "test_plan.h"

static pl_val code_lit(pl_thread* t, pl_val value) {
  return test_app1(t, 0, value);
}

static pl_val code_app(pl_thread* t, pl_val f, pl_val x) {
  return test_app2(t, 0, f, x);
}

static pl_val test_p83(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 83);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

static pl_val sleep_zero_fn(pl_thread* t) {
  size_t base = t->vsp;
  pl_val args[1] = {0};
  pl_vpush(t,
           code_lit(t, test_app(t, ax_s5('S', 'l', 'e', 'e', 'p'), 1, args)));
  pl_vpush(t, code_lit(t, test_p83(t)));
  pl_vpush(t, code_app(t, t->vstack[base + 1], t->vstack[base]));
  pl_val fn = test_law(t, 1, 0, t->vstack[base + 2]);
  t->vsp = base;
  return fn;
}

static int run_actor_stress(void) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){.quantum = 2});
  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 4});
  int status = 0;

  enum { NWAVES = 8, NACTORS = 32 };
  for (int wave = 0; wave < NWAVES && status == 0; wave++) {
    er_actor* actors[NACTORS];
    for (int i = 0; i < NACTORS; i++) {
      actors[i] = er_scheduler_actor(sys);
      pl_thread* t = er_actor_thread(actors[i]);
      er_actor_start(actors[i], sleep_zero_fn(t));
    }
    if (er_mt_executor_run(ex) != ER_RUN_IDLE) {
      fprintf(stderr, "actor wave %d did not reach idle\n", wave);
      status = 1;
      break;
    }
    for (int i = 0; i < NACTORS; i++) {
      if (er_actor_state(actors[i]) != ER_ACTOR_HALTED) {
        fprintf(stderr, "actor %d in wave %d did not halt\n", i, wave);
        status = 1;
        break;
      }
    }
  }

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  return status;
}

TEST(actor_tsan, repeated_multithreaded_waves_reach_idle) {
  ASSERT_EQ(run_actor_stress(), 0);
}
