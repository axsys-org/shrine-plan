#ifndef ENKI_TESTS_SUPPORT_FFF_H
#define ENKI_TESTS_SUPPORT_FFF_H

#include <stddef.h>

#define FFF_ARG_HISTORY_LEN 50u

#define DEFINE_FFF_GLOBALS typedef int fff_globals_t

#define RESET_FAKE(function_name) function_name##_reset()

#define FFF_CONCAT_INNER(a, b)                 a##b
#define FFF_CONCAT(a, b)                       FFF_CONCAT_INNER(a, b)
#define FFF_NARG_INNER(_1, _2, _3, count, ...) count
#define FFF_NARG(...)                          FFF_NARG_INNER(__VA_ARGS__, 3, 2, 1)

#define FAKE_VALUE_FUNC(return_type, function_name, ...)                       \
  FFF_CONCAT(FAKE_VALUE_FUNC_, FFF_NARG(__VA_ARGS__))                          \
  (return_type, function_name, __VA_ARGS__)

#define FAKE_VOID_FUNC(function_name, ...)                                     \
  FFF_CONCAT(FAKE_VOID_FUNC_, FFF_NARG(__VA_ARGS__))(function_name, __VA_ARGS__)

#define FAKE_VALUE_FUNC_2(return_type, function_name, arg0_type, arg1_type)    \
  typedef struct function_name##_fake_t {                                      \
    unsigned int call_count;                                                   \
    arg0_type arg0_val;                                                        \
    arg1_type arg1_val;                                                        \
    arg0_type arg0_history[FFF_ARG_HISTORY_LEN];                               \
    arg1_type arg1_history[FFF_ARG_HISTORY_LEN];                               \
    return_type return_val;                                                    \
    return_type (*custom_fake)(arg0_type arg0, arg1_type arg1);                \
  } function_name##_fake_t;                                                    \
  static function_name##_fake_t function_name##_fake;                          \
  static void function_name##_reset(void) {                                    \
    function_name##_fake = (function_name##_fake_t){0};                        \
  }                                                                            \
  static return_type function_name(arg0_type arg0, arg1_type arg1) {           \
    size_t index = function_name##_fake.call_count;                            \
    function_name##_fake.call_count += 1;                                      \
    function_name##_fake.arg0_val = arg0;                                      \
    function_name##_fake.arg1_val = arg1;                                      \
    if (index < FFF_ARG_HISTORY_LEN) {                                         \
      function_name##_fake.arg0_history[index] = arg0;                         \
      function_name##_fake.arg1_history[index] = arg1;                         \
    }                                                                          \
    if (function_name##_fake.custom_fake != NULL) {                            \
      return function_name##_fake.custom_fake(arg0, arg1);                     \
    }                                                                          \
    return function_name##_fake.return_val;                                    \
  }                                                                            \
  typedef int function_name##_fake_semicolon_t

#define FAKE_VALUE_FUNC_3(return_type, function_name, arg0_type, arg1_type,    \
                          arg2_type)                                           \
  typedef struct function_name##_fake_t {                                      \
    unsigned int call_count;                                                   \
    arg0_type arg0_val;                                                        \
    arg1_type arg1_val;                                                        \
    arg2_type arg2_val;                                                        \
    arg0_type arg0_history[FFF_ARG_HISTORY_LEN];                               \
    arg1_type arg1_history[FFF_ARG_HISTORY_LEN];                               \
    arg2_type arg2_history[FFF_ARG_HISTORY_LEN];                               \
    return_type return_val;                                                    \
    return_type (*custom_fake)(arg0_type arg0, arg1_type arg1,                 \
                               arg2_type arg2);                                \
  } function_name##_fake_t;                                                    \
  static function_name##_fake_t function_name##_fake;                          \
  static void function_name##_reset(void) {                                    \
    function_name##_fake = (function_name##_fake_t){0};                        \
  }                                                                            \
  static return_type function_name(arg0_type arg0, arg1_type arg1,             \
                                   arg2_type arg2) {                           \
    size_t index = function_name##_fake.call_count;                            \
    function_name##_fake.call_count += 1;                                      \
    function_name##_fake.arg0_val = arg0;                                      \
    function_name##_fake.arg1_val = arg1;                                      \
    function_name##_fake.arg2_val = arg2;                                      \
    if (index < FFF_ARG_HISTORY_LEN) {                                         \
      function_name##_fake.arg0_history[index] = arg0;                         \
      function_name##_fake.arg1_history[index] = arg1;                         \
      function_name##_fake.arg2_history[index] = arg2;                         \
    }                                                                          \
    if (function_name##_fake.custom_fake != NULL) {                            \
      return function_name##_fake.custom_fake(arg0, arg1, arg2);               \
    }                                                                          \
    return function_name##_fake.return_val;                                    \
  }                                                                            \
  typedef int function_name##_fake_semicolon_t

#define FAKE_VOID_FUNC_2(function_name, arg0_type, arg1_type)                  \
  typedef struct function_name##_fake_t {                                      \
    unsigned int call_count;                                                   \
    arg0_type arg0_val;                                                        \
    arg1_type arg1_val;                                                        \
    arg0_type arg0_history[FFF_ARG_HISTORY_LEN];                               \
    arg1_type arg1_history[FFF_ARG_HISTORY_LEN];                               \
    void (*custom_fake)(arg0_type arg0, arg1_type arg1);                       \
  } function_name##_fake_t;                                                    \
  static function_name##_fake_t function_name##_fake;                          \
  static void function_name##_reset(void) {                                    \
    function_name##_fake = (function_name##_fake_t){0};                        \
  }                                                                            \
  static void function_name(arg0_type arg0, arg1_type arg1) {                  \
    size_t index = function_name##_fake.call_count;                            \
    function_name##_fake.call_count += 1;                                      \
    function_name##_fake.arg0_val = arg0;                                      \
    function_name##_fake.arg1_val = arg1;                                      \
    if (index < FFF_ARG_HISTORY_LEN) {                                         \
      function_name##_fake.arg0_history[index] = arg0;                         \
      function_name##_fake.arg1_history[index] = arg1;                         \
    }                                                                          \
    if (function_name##_fake.custom_fake != NULL) {                            \
      function_name##_fake.custom_fake(arg0, arg1);                            \
    }                                                                          \
  }                                                                            \
  typedef int function_name##_fake_semicolon_t

#endif
