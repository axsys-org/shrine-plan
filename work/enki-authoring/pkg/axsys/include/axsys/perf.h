#ifndef AX_PERF_H
#define AX_PERF_H

#define ax_likely(x)   __builtin_expect(!!(x), 1)
#define ax_unlikely(x) __builtin_expect(!!(x), 0)

#endif
