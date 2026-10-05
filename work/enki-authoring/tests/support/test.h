#ifndef ENKI_TEST_H
#define ENKI_TEST_H

#define GREATEST_USE_ABBREVS 0
#define GREATEST_USE_LONGJMP 1
#include "greatest.h"

#include <signal.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef ENKI_TEST_TIMEOUT_SECONDS
#define ENKI_TEST_TIMEOUT_SECONDS 60
#endif

#define ENKI_TEST_STRINGIFY_(VALUE) #VALUE
#define ENKI_TEST_STRINGIFY(VALUE)  ENKI_TEST_STRINGIFY_(VALUE)

enum {
  ENKI_TEST_MAX_SUITES = 16,
  ENKI_TEST_MAX_CASES = 128,
  ENKI_TEST_MESSAGE_SIZE = 1024,
};

typedef void enki_test_fn(void);
typedef void enki_test_fixture_fn(void);

typedef struct enki_test_suite {
  const char* name;
  enki_test_fixture_fn* setup;
  enki_test_fixture_fn* teardown;
} enki_test_suite;

typedef struct enki_test_case {
  size_t suite;
  const char* name;
  enki_test_fn* function;
} enki_test_case;

static enki_test_suite enki_test_suites[ENKI_TEST_MAX_SUITES];
static enki_test_case enki_test_cases[ENKI_TEST_MAX_CASES];
static size_t enki_test_suite_count;
static size_t enki_test_case_count;
static size_t enki_test_active_suite;
static char enki_test_message[ENKI_TEST_MESSAGE_SIZE];

static size_t enki_test_get_suite(const char* name);
static void enki_test_register(const char* suite, const char* name,
                               enki_test_fn* function);
static void enki_test_register_fixture(const char* suite,
                                       enki_test_fixture_fn* setup,
                                       enki_test_fixture_fn* teardown);

static void enki_test_abort_registry(const char* kind, const char* name) {
  fprintf(stderr, "greatest: too many registered %s (%s)\n", kind, name);
  abort();
}

static size_t enki_test_get_suite(const char* name) {
  for (size_t i = 0; i < enki_test_suite_count; i++) {
    if (strcmp(enki_test_suites[i].name, name) == 0) {
      return i;
    }
  }
  if (enki_test_suite_count == ENKI_TEST_MAX_SUITES) {
    enki_test_abort_registry("suites", name);
  }
  size_t suite = enki_test_suite_count++;
  enki_test_suites[suite] = (enki_test_suite){
      .name = name,
      .setup = NULL,
      .teardown = NULL,
  };
  return suite;
}

static void enki_test_register(const char* suite, const char* name,
                               enki_test_fn* function) {
  if (enki_test_case_count == ENKI_TEST_MAX_CASES) {
    enki_test_abort_registry("tests", name);
  }
  enki_test_cases[enki_test_case_count++] = (enki_test_case){
      .suite = enki_test_get_suite(suite),
      .name = name,
      .function = function,
  };
}

static void enki_test_register_fixture(const char* suite,
                                       enki_test_fixture_fn* setup,
                                       enki_test_fixture_fn* teardown) {
  enki_test_suite* registered = &enki_test_suites[enki_test_get_suite(suite)];
  registered->setup = setup;
  registered->teardown = teardown;
}

static void enki_test_fail(const char* file, unsigned int line,
                           const char* expression, const char* format, ...) {
  size_t used = 0;
  int written =
      snprintf(enki_test_message, sizeof(enki_test_message), "%s", expression);
  if (written > 0) {
    used = (size_t)written;
    if (used >= sizeof(enki_test_message)) {
      used = sizeof(enki_test_message) - 1;
    }
  }
  if (format[0] != '\0' && used + 2 < sizeof(enki_test_message)) {
    enki_test_message[used++] = ':';
    enki_test_message[used++] = ' ';
    enki_test_message[used] = '\0';
    va_list args;
    va_start(args, format);
    (void)vsnprintf(enki_test_message + used, sizeof(enki_test_message) - used,
                    format, args);
    va_end(args);
  }
  greatest_info.fail_file = file;
  greatest_info.fail_line = line;
  greatest_info.msg = enki_test_message;
  longjmp(greatest_info.jump_dest, GREATEST_TEST_RES_FAIL);
}

static void enki_test_skip(const char* message) {
  greatest_info.msg = message;
  longjmp(greatest_info.jump_dest, GREATEST_TEST_RES_SKIP);
}

#define ENKI_TEST_CONCAT_(LEFT, RIGHT)       LEFT##RIGHT
#define ENKI_TEST_CONCAT(LEFT, RIGHT)        ENKI_TEST_CONCAT_(LEFT, RIGHT)
#define ENKI_TEST_NAME(SUITE, NAME)          enki_test_##SUITE##_##NAME
#define ENKI_TEST_REGISTER_NAME(SUITE, NAME) enki_test_register_##SUITE##_##NAME
#define ENKI_TEST_FIXTURE_NAME(SUITE)        enki_test_fixture_##SUITE

#define TEST(SUITE, NAME, ...)                                                 \
  static void ENKI_TEST_NAME(SUITE, NAME)(void);                               \
  static void ENKI_TEST_REGISTER_NAME(SUITE, NAME)(void)                       \
      __attribute__((constructor));                                            \
  static void ENKI_TEST_REGISTER_NAME(SUITE, NAME)(void) {                     \
    enki_test_register(#SUITE, #NAME, ENKI_TEST_NAME(SUITE, NAME));            \
  }                                                                            \
  static void ENKI_TEST_NAME(SUITE, NAME)(void)

#define TEST_FIXTURE(SUITE, SETUP, TEARDOWN)                                   \
  static void ENKI_TEST_FIXTURE_NAME(SUITE)(void)                              \
      __attribute__((constructor));                                            \
  static void ENKI_TEST_FIXTURE_NAME(SUITE)(void) {                            \
    enki_test_register_fixture(#SUITE, SETUP, TEARDOWN);                       \
  }

#define ENKI_TEST_ASSERT(CONDITION, EXPRESSION, ...)                           \
  do {                                                                         \
    greatest_info.assertions++;                                                \
    if (!(CONDITION)) {                                                        \
      enki_test_fail(__FILE__, __LINE__, EXPRESSION,                           \
                     "" __VA_OPT__(__VA_ARGS__));                              \
    }                                                                          \
  } while (0)

#define ASSERT(CONDITION, ...)                                                 \
  ENKI_TEST_ASSERT(CONDITION, #CONDITION, __VA_ARGS__)
#define ASSERT_FALSE(CONDITION, ...)                                           \
  ENKI_TEST_ASSERT(!(CONDITION), "!(" #CONDITION ")", __VA_ARGS__)
#define ASSERT_EQ(LEFT, RIGHT, ...)                                            \
  ENKI_TEST_ASSERT((LEFT) == (RIGHT), #LEFT " == " #RIGHT, __VA_ARGS__)
#define ASSERT_NEQ(LEFT, RIGHT, ...)                                           \
  ENKI_TEST_ASSERT((LEFT) != (RIGHT), #LEFT " != " #RIGHT, __VA_ARGS__)
#define ASSERT_GT(LEFT, RIGHT, ...)                                            \
  ENKI_TEST_ASSERT((LEFT) > (RIGHT), #LEFT " > " #RIGHT, __VA_ARGS__)
#define ASSERT_GTE(LEFT, RIGHT, ...)                                           \
  ENKI_TEST_ASSERT((LEFT) >= (RIGHT), #LEFT " >= " #RIGHT, __VA_ARGS__)
#define ASSERT_LT(LEFT, RIGHT, ...)                                            \
  ENKI_TEST_ASSERT((LEFT) < (RIGHT), #LEFT " < " #RIGHT, __VA_ARGS__)
#define ASSERT_LTE(LEFT, RIGHT, ...)                                           \
  ENKI_TEST_ASSERT((LEFT) <= (RIGHT), #LEFT " <= " #RIGHT, __VA_ARGS__)
#define ASSERT_NULL(VALUE, ...)                                                \
  ENKI_TEST_ASSERT((VALUE) == NULL, #VALUE " == NULL", __VA_ARGS__)
#define ASSERT_NOT_NULL(VALUE, ...)                                            \
  ENKI_TEST_ASSERT((VALUE) != NULL, #VALUE " != NULL", __VA_ARGS__)
#define ASSERT_STR_EQ(LEFT, RIGHT, ...)                                        \
  ENKI_TEST_ASSERT(strcmp(LEFT, RIGHT) == 0, #LEFT " == " #RIGHT, __VA_ARGS__)
#define ASSERT_MEM_EQ(LEFT, RIGHT, SIZE, ...)                                  \
  ENKI_TEST_ASSERT(memcmp(LEFT, RIGHT, SIZE) == 0, #LEFT " == " #RIGHT,        \
                   __VA_ARGS__)
#define FAIL_TEST(...)                                                         \
  enki_test_fail(__FILE__, __LINE__, "explicit failure",                       \
                 "" __VA_OPT__(__VA_ARGS__))
#define SKIP_TEST(MESSAGE) enki_test_skip(MESSAGE)

GREATEST_MAIN_DEFS();

static void enki_test_timeout(int signal_number) {
  (void)signal_number;
  static const char message[] =
      "\ngreatest: test process timed out after " ENKI_TEST_STRINGIFY(
          ENKI_TEST_TIMEOUT_SECONDS) " seconds\n";
  /* glibc marks write() warn-unused-result; assigning satisfies it */
  ssize_t ignored = write(STDERR_FILENO, message, sizeof(message) - 1);
  (void)ignored;
  _exit(124);
}

static void enki_test_teardown(void* data) {
  (void)data;
  enki_test_suite* suite = &enki_test_suites[enki_test_active_suite];
  if (suite->teardown != NULL) {
    suite->teardown();
  }
}

static void enki_test_run_suite(void) {
  enki_test_suite* suite = &enki_test_suites[enki_test_active_suite];
  GREATEST_SET_TEARDOWN_CB(suite->teardown == NULL ? NULL : enki_test_teardown,
                           NULL);
  for (size_t i = 0; i < enki_test_case_count; i++) {
    enki_test_case* test = &enki_test_cases[i];
    if (test->suite != enki_test_active_suite) {
      continue;
    }
    if (greatest_test_pre(test->name) == 1) {
      enum greatest_test_res result = GREATEST_SAVE_CONTEXT();
      if (result == GREATEST_TEST_RES_PASS) {
        if (suite->setup != NULL) {
          suite->setup();
        }
        test->function();
      }
      greatest_test_post(result);
    }
  }
}

int main(int argc, char** argv) {
  if (signal(SIGALRM, enki_test_timeout) == SIG_ERR) {
    perror("greatest: cannot install test timeout");
    return EXIT_FAILURE;
  }
  (void)alarm(ENKI_TEST_TIMEOUT_SECONDS);
  GREATEST_MAIN_BEGIN();
  for (size_t i = 0; i < enki_test_suite_count; i++) {
    enki_test_active_suite = i;
    greatest_run_suite(enki_test_run_suite, enki_test_suites[i].name);
  }
  (void)alarm(0);
  GREATEST_MAIN_END();
}

#endif
