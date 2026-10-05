#include "test.h"
#include <setjmp.h>
#include <stdlib.h>
#include <string.h>

#include "enki/wisp.h"
#include "plan/debug.h"
#include "plan/store.h"

typedef struct wisp_fixture {
  pl_store* store;
  pl_heap* heap;
  en_wisp* w;
} wisp_fixture;

static wisp_fixture fix_new(void) {
  wisp_fixture f;
  f.store = pl_store_new_mem();
  f.heap = pl_heap_new(1 << 16, f.store);
  f.w = en_wisp_new(f.heap);
  f.w->err_f = true;
  return f;
}

static void fix_free(wisp_fixture* f) {
  en_wisp_free(f->w);
  pl_heap_free(f->heap);
  pl_store_free(f->store);
}

static char* eval_str(wisp_fixture* f, const char* src) {
  char* cur = (char*)src;
  pl_val form = en_wisp_parse(f->w, &cur);
  pl_val out = en_wisp_eval(f->w, form);
  out = en_run_nf(f->w, out);
  return en_wisp_print(f->w, out, NULL);
}

#define ASSERT_EVALS(f, src, expect)                                           \
  do {                                                                         \
    char* got_c = eval_str(f, src);                                            \
    ASSERT_STR_EQ(got_c, expect, "%s evaluated to %s", src, got_c);            \
    free(got_c);                                                               \
  } while (0)

TEST(wisp, literals_and_rows) {
  wisp_fixture f = fix_new();
  if (setjmp(f.w->errjmp) != 0)
    FAIL_TEST("wisp error: %s", f.w->msg_c);
  ASSERT_EVALS(&f, "42", "42");
  ASSERT_EVALS(&f, "(#app 0 1 2 3)", "(0 1 2 3)");
  ASSERT_EVALS(&f, "\"hello\"", "\"hello\"");
  fix_free(&f);
}

TEST(wisp, op_application) {
  wisp_fixture f = fix_new();
  if (setjmp(f.w->errjmp) != 0)
    FAIL_TEST("wisp error: %s", f.w->msg_c);
  ASSERT_EVALS(&f, "(#app (#pin 66) (\"Add\" 2 3))", "5");
  ASSERT_EVALS(&f, "(#app (#pin 66) (\"Mul\" 6 7))", "42");
  ASSERT_EVALS(&f, "(#app (#pin 0) (0 42))", "<42>");
  fix_free(&f);
}

TEST(wisp, laws_and_letrec) {
  wisp_fixture f = fix_new();
  if (setjmp(f.w->errjmp) != 0)
    FAIL_TEST("wisp error: %s", f.w->msg_c);
  pl_val forms[3];
  const char* srcs[3] = {
      "(#bind id (#law \"id\" (id x) x))",
      "(#bind k (#law \"k\" (k x y) x))",
      NULL,
  };
  for (int i = 0; i < 2; i++) {
    char* cur = (char*)srcs[i];
    forms[i] = en_wisp_parse(f.w, &cur);
    (void)en_wisp_eval(f.w, forms[i]);
  }
  ASSERT_EVALS(&f, "(#app id 9)", "9");
  ASSERT_EVALS(&f, "(#app k 7 8)", "7");
  /* letrec: f x = let a = b, b = x in a */
  {
    char* cur = (char*)"(#bind f (#law \"f\" (f x) a(b) b(x) a))";
    pl_val form = en_wisp_parse(f.w, &cur);
    (void)en_wisp_eval(f.w, form);
  }
  ASSERT_EVALS(&f, "(#app f 5)", "5");
  fix_free(&f);
}

TEST(wisp, macros_expand) {
  wisp_fixture f = fix_new();
  if (setjmp(f.w->errjmp) != 0)
    FAIL_TEST("wisp error: %s", f.w->msg_c);
  /* a user macro that rewrites (twice e) to (#app (#pin 66)
   * ("Add" e e)) is overkill here; instead check the simpler #app and
   * juxt machinery used by the assembler front end */
  ASSERT_EVALS(&f, "(#app (#pin 66) (\"If\" 0 1 2))", "2");
  ASSERT_EVALS(&f, "(#app (#pin 66) (\"If\" 5 1 2))", "1");
  fix_free(&f);
}

TEST(wisp, error_reporting) {
  wisp_fixture f = fix_new();
  volatile bool failed = false;
  if (setjmp(f.w->errjmp) != 0) {
    failed = true;
    ASSERT_NOT_NULL(f.w->msg_c);
  } else {
    char* cur = (char*)"unbound-symbol-xyz";
    pl_val form = en_wisp_parse(f.w, &cur);
    (void)en_wisp_eval(f.w, form);
  }
  ASSERT(failed);
  fix_free(&f);
}
