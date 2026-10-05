#ifndef AX_PROFILE_H
#define AX_PROFILE_H

#if defined(TRACY_ENABLE) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * Optional Chrome Trace JSON sink.  The sink is process-global and must be
 * started before worker threads begin emitting events, then finished after
 * they have quiesced.  Event timestamps are monotonic microseconds relative
 * to ax_profile_json_start().
 */
bool ax_profile_json_start(const char* path);
bool ax_profile_json_enabled(void);
void ax_profile_json_thread_name(uint64_t tid, const char* name, size_t name_n);
void ax_profile_json_zone_begin(uint64_t tid, uint64_t zone,
                                const uint8_t* name, size_t name_n);
void ax_profile_json_zone_end(uint64_t tid, uint64_t zone, const uint8_t* name,
                              size_t name_n);
/* Internal runtime spans.  Unlike explicit SPLAN zones, callers supply the
 * Chrome Trace category and an opaque span identity. */
void ax_profile_json_span_begin(uint64_t tid, uint64_t span,
                                const uint8_t* category, size_t category_n,
                                const uint8_t* name, size_t name_n);
void ax_profile_json_span_end(uint64_t tid, uint64_t span,
                              const uint8_t* category, size_t category_n,
                              const uint8_t* name, size_t name_n);
/* Flushes and closes the sink.  False reports any write/close failure. */
bool ax_profile_json_finish(void);

#ifdef TRACY_ENABLE
#include <tracy/TracyC.h>
#include <time.h>
#include <stdlib.h>

typedef TracyCZoneCtx ax_profile_zone_ctx;

static inline double ax_now_s(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
    abort();
  return (double)ts.tv_sec + ((double)ts.tv_nsec / 1000000000.0);
}

static inline void ax_profile_zone_end(ax_profile_zone_ctx* ctx) {
  TracyCZoneEnd(*ctx);
}

static void ax_wait_for_tracy(double tim_df) {
  double deadline_s = ax_now_s() + tim_df;
  const struct timespec sleep_ts = {.tv_sec = 0, .tv_nsec = 10000000L};
  while (!TracyCIsConnected && ax_now_s() < deadline_s) {
    nanosleep(&sleep_ts, NULL);
  }
}

#define AX_PROFILE_JOIN2(a, b) a##b
#define AX_PROFILE_JOIN(a, b)  AX_PROFILE_JOIN2(a, b)
#define AX_PROFILE_ZONE_IMPL(name, line)                                       \
  TracyCZoneN(AX_PROFILE_JOIN(ax_tracy_zone_, line), name, TracyCIsConnected); \
  __attribute__((cleanup(ax_profile_zone_end))) ax_profile_zone_ctx            \
  AX_PROFILE_JOIN(ax_tracy_zone_cleanup_, line) =                              \
      AX_PROFILE_JOIN(ax_tracy_zone_, line)

#define AX_PROFILE_ZONE(name) AX_PROFILE_ZONE_IMPL(name, __LINE__)
#define AX_PROFILE_ZONE_BEGIN(ctx, name)                                       \
  TracyCZoneN(ctx, name, TracyCIsConnected)
#define AX_PROFILE_ZONE_BEGIN_ASSIGN(ctx, name)                                \
  do {                                                                         \
    static const struct ___tracy_source_location_data AX_PROFILE_JOIN(         \
        ax_tracy_source_, __LINE__) = {name, __func__, TracyFile,              \
                                       (uint32_t)TracyLine, 0};                \
    (ctx) = ___tracy_emit_zone_begin(                                          \
        &AX_PROFILE_JOIN(ax_tracy_source_, __LINE__), TracyCIsConnected);      \
  } while (0)
#define AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME_ACTIVE(ctx, name, size, active)     \
  do {                                                                         \
    static const struct ___tracy_source_location_data AX_PROFILE_JOIN(         \
        ax_tracy_source_, __LINE__) = {NULL, __func__, TracyFile,              \
                                       (uint32_t)TracyLine, 0};                \
    bool AX_PROFILE_JOIN(ax_tracy_active_, __LINE__) =                         \
        TracyCIsConnected && (active);                                         \
    (ctx) =                                                                    \
        ___tracy_emit_zone_begin(&AX_PROFILE_JOIN(ax_tracy_source_, __LINE__), \
                                 AX_PROFILE_JOIN(ax_tracy_active_, __LINE__)); \
    if (AX_PROFILE_JOIN(ax_tracy_active_, __LINE__))                           \
      TracyCZoneName(ctx, name, size);                                         \
  } while (0)
#define AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME(ctx, name, size)                    \
  AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME_ACTIVE(ctx, name, size, true)
#define AX_PROFILE_ZONE_BEGIN_ALLOC_NAME(ctx, name, size)                      \
  AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME(ctx, name, size)
#define AX_PROFILE_ZONE_END(ctx)              TracyCZoneEnd(ctx)
#define AX_PROFILE_ZONE_NAME(ctx, name, size) TracyCZoneName(ctx, name, size)
#define AX_PROFILE_THREAD(name)               TracyCSetThreadName(name)
#define AX_PROFILE_FRAME(name)                TracyCFrameMarkNamed(name)
#define AX_PROFILE_PLOT_I(name, value)        TracyCPlotI(name, value)

#else

typedef const void* ax_profile_zone_ctx;

#define AX_PROFILE_ZONE(name)                   ((void)0)
#define AX_PROFILE_ZONE_BEGIN(ctx, name)        ((void)0)
#define AX_PROFILE_ZONE_BEGIN_ASSIGN(ctx, name) ((void)0)
#define AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME_ACTIVE(ctx, name, size, active)     \
  ((void)0)
#define AX_PROFILE_ZONE_BEGIN_DYNAMIC_NAME(ctx, name, size) ((void)0)
#define AX_PROFILE_ZONE_BEGIN_ALLOC_NAME(ctx, name, size)   ((void)0)
#define AX_PROFILE_ZONE_END(ctx)                            ((void)0)
#define AX_PROFILE_ZONE_NAME(ctx, name, size)               ((void)0)
#define AX_PROFILE_THREAD(name)                             ((void)0)
#define AX_PROFILE_FRAME(name)                              ((void)0)
#define AX_PROFILE_PLOT_I(name, value)                      ((void)0)

static void ax_wait_for_tracy(double tim_df) {
  (void)tim_df;
}

#endif
#endif
