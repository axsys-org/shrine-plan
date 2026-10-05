/*
    axsys/sb.h - tiny deferred string builder / flat twine

    public domain-ish single header, in the style of stb libraries.
    no warranty, etc.

    usage:

        #define AX_SB_IMPLEMENTATION
        #include "axsys/sb.h"

    notes:

        - appended strings are referenced, not copied.
        - caller must keep referenced string bytes alive until materialization.
        - append_cstr() captures strlen() at append time.
        - materialized output is always NUL-terminated, but may contain embedded
   NULs.
        - do not memcpy/copy an initialized builder by value; it has internal
   storage.
*/

#ifndef AX_SB_H
#define AX_SB_H

#include <stddef.h>
#include <stdint.h>
#include "axsys/allocator.h"

#ifndef AX_SB_INLINE_PIECES
#define AX_SB_INLINE_PIECES 16
#endif

#if AX_SB_INLINE_PIECES < 1
#error AX_SB_INLINE_PIECES must be at least 1
#endif

#ifndef AX_SB_API
#ifdef AX_SB_STATIC
#define AX_SB_API static
#else
#define AX_SB_API extern
#endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ax_sb_ref {
  const char* data;
  size_t len;
} ax_sb_ref;

typedef enum ax_sb_piece_kind {
  AX_SB_PIECE_REF = 1,
  AX_SB_PIECE_CHAR = 2,
  AX_SB_PIECE_I64 = 3,
  AX_SB_PIECE_U64 = 4
} ax_sb_piece_kind;

typedef struct ax_sb_piece {
  unsigned char kind;
  unsigned char base;
  unsigned char uppercase;
  unsigned char _pad;

  union {
    ax_sb_ref ref;
    char ch;
    int64_t i64;
    uint64_t u64;
  } u;
} ax_sb_piece;

typedef struct ax_sb {
  const ax_allocator* allocator;

  ax_sb_piece* pieces;
  size_t count;
  size_t capacity;
  int failed;

  ax_sb_piece inline_pieces[AX_SB_INLINE_PIECES];
} ax_sb;

/* string-literal helper. intentionally only works with narrow string literals.
 */
#define ax_sb_append_lit(sb, literal)                                          \
  ax_sb_append_ref((sb), "" literal, sizeof(literal) - 1u)

/* lifecycle */
AX_SB_API void ax_sb_init(ax_sb* sb, const ax_allocator* allocator);
AX_SB_API void ax_sb_reset(ax_sb* sb);
AX_SB_API void ax_sb_free(ax_sb* sb);

/* status */
AX_SB_API int ax_sb_failed(const ax_sb* sb);
AX_SB_API size_t ax_sb_piece_count(const ax_sb* sb);

/* optional preallocation for metadata pieces, not bytes */
AX_SB_API int ax_sb_reserve_pieces(ax_sb* sb, size_t additional_piece_count);

/* appending */
AX_SB_API int ax_sb_append_ref(ax_sb* sb, const char* data, size_t len);
AX_SB_API int ax_sb_append_cstr(ax_sb* sb, const char* cstr);
AX_SB_API int ax_sb_append_char(ax_sb* sb, char c);
AX_SB_API int ax_sb_append_i64(ax_sb* sb, int64_t value);
AX_SB_API int ax_sb_append_u64(ax_sb* sb, uint64_t value);
AX_SB_API int ax_sb_append_u64_base(ax_sb* sb, uint64_t value, unsigned base,
                                    int uppercase);

/* copies only metadata pieces, not referenced string bytes */
AX_SB_API int ax_sb_append_builder(ax_sb* sb, const ax_sb* other);

/* flattening */
AX_SB_API int ax_sb_measure(const ax_sb* sb, size_t* out_len);
AX_SB_API int ax_sb_write(const ax_sb* sb, char* dst, size_t dst_size,
                          size_t* out_len);
AX_SB_API char* ax_sb_build(const ax_sb* sb, size_t* out_len);
AX_SB_API char* ax_sb_build_with_allocator(const ax_sb* sb,
                                           const ax_allocator* allocator,
                                           size_t* out_len);

#if defined(AX_SB_IMPLEMENTATION)

#include <string.h>

#ifndef SIZE_MAX
#define SIZE_MAX ((size_t)-1)
#endif

static int ax_sb__allocator_ok(const ax_allocator* a) {
  return a != NULL && a->alloc != 0 && a->free != 0;
}

static int ax_sb__grow(ax_sb* sb, size_t wanted_capacity) {
  size_t new_capacity;
  size_t bytes;
  ax_sb_piece* new_pieces;

  if (!sb || sb->failed)
    return 0;

  if (wanted_capacity <= sb->capacity)
    return 1;

  if (!ax_sb__allocator_ok(sb->allocator)) {
    sb->failed = 1;
    return 0;
  }

  new_capacity = sb->capacity ? sb->capacity : AX_SB_INLINE_PIECES;

  while (new_capacity < wanted_capacity) {
    if (new_capacity > SIZE_MAX / 2u) {
      new_capacity = wanted_capacity;
      break;
    }
    new_capacity *= 2u;
  }

  if (new_capacity > SIZE_MAX / sizeof(ax_sb_piece)) {
    sb->failed = 1;
    return 0;
  }

  bytes = new_capacity * sizeof(ax_sb_piece);

  if (sb->pieces == sb->inline_pieces) {
    new_pieces = (ax_sb_piece*)sb->allocator->alloc(sb->allocator->ctx, bytes);
    if (!new_pieces) {
      sb->failed = 1;
      return 0;
    }

    if (sb->count)
      memcpy(new_pieces, sb->inline_pieces, sb->count * sizeof(ax_sb_piece));
  } else if (sb->allocator->realloc) {
    new_pieces = (ax_sb_piece*)sb->allocator->realloc(sb->allocator->ctx,
                                                      sb->pieces, bytes);
    if (!new_pieces) {
      sb->failed = 1;
      return 0;
    }
  } else {
    new_pieces = (ax_sb_piece*)sb->allocator->alloc(sb->allocator->ctx, bytes);
    if (!new_pieces) {
      sb->failed = 1;
      return 0;
    }

    if (sb->count)
      memcpy(new_pieces, sb->pieces, sb->count * sizeof(ax_sb_piece));

    sb->allocator->free(sb->allocator->ctx, sb->pieces);
  }

  sb->pieces = new_pieces;
  sb->capacity = new_capacity;
  return 1;
}

static int ax_sb__push(ax_sb* sb, ax_sb_piece piece) {
  if (!sb || sb->failed)
    return 0;

  if (sb->count == sb->capacity) {
    if (!ax_sb__grow(sb, sb->count + 1u))
      return 0;
  }

  sb->pieces[sb->count++] = piece;
  return 1;
}

static size_t ax_sb__u64_len(uint64_t value, unsigned base) {
  size_t n = 1;

  while (value >= (uint64_t)base) {
    value /= (uint64_t)base;
    ++n;
  }

  return n;
}

static char* ax_sb__emit_u64(char* dst, uint64_t value, unsigned base,
                             int uppercase) {
  char tmp[64];
  size_t n = 0;
  const char* digits = uppercase ? "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                                 : "0123456789abcdefghijklmnopqrstuvwxyz";

  do {
    tmp[n++] = digits[value % (uint64_t)base];
    value /= (uint64_t)base;
  } while (value);

  while (n)
    *dst++ = tmp[--n];

  return dst;
}

static uint64_t ax_sb__abs_i64_to_u64(int64_t value) {
  if (value < 0)
    return (uint64_t)(-(value + 1)) + 1u;

  return (uint64_t)value;
}

static size_t ax_sb__i64_len(int64_t value) {
  size_t n = ax_sb__u64_len(ax_sb__abs_i64_to_u64(value), 10);
  return value < 0 ? n + 1u : n;
}

static char* ax_sb__emit_i64(char* dst, int64_t value) {
  if (value < 0)
    *dst++ = '-';

  return ax_sb__emit_u64(dst, ax_sb__abs_i64_to_u64(value), 10, 0);
}

AX_SB_API void ax_sb_init(ax_sb* sb, const ax_allocator* allocator) {
  if (!sb)
    return;

  sb->allocator = allocator;
  sb->pieces = sb->inline_pieces;
  sb->count = 0;
  sb->capacity = AX_SB_INLINE_PIECES;
  sb->failed = !ax_sb__allocator_ok(allocator);
}

AX_SB_API void ax_sb_reset(ax_sb* sb) {
  if (!sb)
    return;

  sb->count = 0;
  sb->failed = !ax_sb__allocator_ok(sb->allocator);
}

AX_SB_API void ax_sb_free(ax_sb* sb) {
  const ax_allocator* allocator;

  if (!sb)
    return;

  allocator = sb->allocator;

  if (sb->pieces && sb->pieces != sb->inline_pieces && allocator->free)
    allocator->free(allocator->ctx, sb->pieces);

  sb->allocator = allocator;
  sb->pieces = sb->inline_pieces;
  sb->count = 0;
  sb->capacity = AX_SB_INLINE_PIECES;
  sb->failed = !ax_sb__allocator_ok(allocator);
}

AX_SB_API int ax_sb_failed(const ax_sb* sb) {
  return !sb || sb->failed;
}

AX_SB_API size_t ax_sb_piece_count(const ax_sb* sb) {
  return sb ? sb->count : 0u;
}

AX_SB_API int ax_sb_reserve_pieces(ax_sb* sb, size_t additional_piece_count) {
  if (!sb || sb->failed)
    return 0;

  if (additional_piece_count > SIZE_MAX - sb->count) {
    sb->failed = 1;
    return 0;
  }

  return ax_sb__grow(sb, sb->count + additional_piece_count);
}

AX_SB_API int ax_sb_append_ref(ax_sb* sb, const char* data, size_t len) {
  ax_sb_piece piece;

  if (!sb || sb->failed)
    return 0;

  if (len == 0)
    return 1;

  if (!data) {
    sb->failed = 1;
    return 0;
  }

  piece.kind = AX_SB_PIECE_REF;
  piece.base = 0;
  piece.uppercase = 0;
  piece._pad = 0;
  piece.u.ref.data = data;
  piece.u.ref.len = len;

  return ax_sb__push(sb, piece);
}

AX_SB_API int ax_sb_append_cstr(ax_sb* sb, const char* cstr) {
  if (!sb || sb->failed)
    return 0;

  if (!cstr) {
    sb->failed = 1;
    return 0;
  }

  return ax_sb_append_ref(sb, cstr, strlen(cstr));
}

AX_SB_API int ax_sb_append_char(ax_sb* sb, char c) {
  ax_sb_piece piece;

  if (!sb || sb->failed)
    return 0;

  piece.kind = AX_SB_PIECE_CHAR;
  piece.base = 0;
  piece.uppercase = 0;
  piece._pad = 0;
  piece.u.ch = c;

  return ax_sb__push(sb, piece);
}

AX_SB_API int ax_sb_append_i64(ax_sb* sb, int64_t value) {
  ax_sb_piece piece;

  if (!sb || sb->failed)
    return 0;

  piece.kind = AX_SB_PIECE_I64;
  piece.base = 10;
  piece.uppercase = 0;
  piece._pad = 0;
  piece.u.i64 = value;

  return ax_sb__push(sb, piece);
}

AX_SB_API int ax_sb_append_u64(ax_sb* sb, uint64_t value) {
  return ax_sb_append_u64_base(sb, value, 10, 0);
}

AX_SB_API int ax_sb_append_u64_base(ax_sb* sb, uint64_t value, unsigned base,
                                    int uppercase) {
  ax_sb_piece piece;

  if (!sb || sb->failed)
    return 0;

  if (base < 2 || base > 36) {
    sb->failed = 1;
    return 0;
  }

  piece.kind = AX_SB_PIECE_U64;
  piece.base = (unsigned char)base;
  piece.uppercase = uppercase ? 1u : 0u;
  piece._pad = 0;
  piece.u.u64 = value;

  return ax_sb__push(sb, piece);
}

AX_SB_API int ax_sb_append_builder(ax_sb* sb, const ax_sb* other) {
  size_t old_count;

  if (!sb || sb->failed)
    return 0;

  if (!other || other->failed) {
    sb->failed = 1;
    return 0;
  }

  if (other->count == 0)
    return 1;

  old_count = sb->count;

  if (!ax_sb_reserve_pieces(sb, other->count))
    return 0;

  /*
      memmove handles self-append:
          ax_sb_append_builder(&sb, &sb);
  */
  memmove(sb->pieces + old_count, other->pieces,
          other->count * sizeof(ax_sb_piece));

  sb->count = old_count + other->count;
  return 1;
}

AX_SB_API int ax_sb_measure(const ax_sb* sb, size_t* out_len) {
  size_t total = 0;
  size_t i;

  if (out_len)
    *out_len = 0;

  if (!sb || sb->failed)
    return 0;

  for (i = 0; i < sb->count; ++i) {
    const ax_sb_piece* p = &sb->pieces[i];
    size_t len = 0;

    switch ((ax_sb_piece_kind)p->kind) {
    case AX_SB_PIECE_REF:
      len = p->u.ref.len;
      break;

    case AX_SB_PIECE_CHAR:
      len = 1;
      break;

    case AX_SB_PIECE_I64:
      len = ax_sb__i64_len(p->u.i64);
      break;

    case AX_SB_PIECE_U64:
      if (p->base < 2 || p->base > 36)
        return 0;
      len = ax_sb__u64_len(p->u.u64, p->base);
      break;

    default:
      return 0;
    }

    if (len > SIZE_MAX - total)
      return 0;

    total += len;
  }

  if (out_len)
    *out_len = total;

  return 1;
}

AX_SB_API int ax_sb_write(const ax_sb* sb, char* dst, size_t dst_size,
                          size_t* out_len) {
  size_t needed;
  size_t i;
  char* p;

  if (out_len)
    *out_len = 0;

  if (!ax_sb_measure(sb, &needed))
    return 0;

  if (out_len)
    *out_len = needed;

  if (needed == SIZE_MAX)
    return 0;

  if (!dst || dst_size < needed + 1u)
    return 0;

  p = dst;

  for (i = 0; i < sb->count; ++i) {
    const ax_sb_piece* piece = &sb->pieces[i];

    switch ((ax_sb_piece_kind)piece->kind) {
    case AX_SB_PIECE_REF:
      if (piece->u.ref.len) {
        memcpy(p, piece->u.ref.data, piece->u.ref.len);
        p += piece->u.ref.len;
      }
      break;

    case AX_SB_PIECE_CHAR:
      *p++ = piece->u.ch;
      break;

    case AX_SB_PIECE_I64:
      p = ax_sb__emit_i64(p, piece->u.i64);
      break;

    case AX_SB_PIECE_U64:
      p = ax_sb__emit_u64(p, piece->u.u64, piece->base, piece->uppercase);
      break;

    default:
      return 0;
    }
  }

  *p = '\0';
  return 1;
}

AX_SB_API char* ax_sb_build(const ax_sb* sb, size_t* out_len) {
  if (!sb)
    return 0;

  return ax_sb_build_with_allocator(sb, sb->allocator, out_len);
}

AX_SB_API char* ax_sb_build_with_allocator(const ax_sb* sb,
                                           const ax_allocator* allocator,
                                           size_t* out_len) {
  size_t len;
  char* result;

  if (out_len)
    *out_len = 0;

  if (!ax_sb__allocator_ok(allocator))
    return 0;

  if (!ax_sb_measure(sb, &len))
    return 0;

  if (len == SIZE_MAX)
    return 0;

  result = (char*)allocator->alloc(allocator->ctx, len + 1u);
  if (!result)
    return 0;

  if (!ax_sb_write(sb, result, len + 1u, out_len)) {
    allocator->free(allocator->ctx, result);
    return 0;
  }

  return result;
}

#endif /* implementation */

#ifdef __cplusplus
}
#endif

#endif /* AX_SB_H */
