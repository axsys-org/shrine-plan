#include "axsys/allocator.h"

#include "plan/value.h"
#include "plan/nat.h"
#include "plan/xtract.h"

// XX: deduplicate with canon.c
static bool cn_str_byte_ok(uint8_t b) {
  if (b == '\n')
    return true;
  if (b == '"')
    return false;
  return b >= 0x20 && b < 0x7f;
}

bool pl_nat_is_str(pl_val v) {
  size_t n = pl_nat_byte_len(v);
  if (n == 0)
    return false;
  if (n == 1) {
    uint8_t b = pl_nat_byte_at(v, 0);
    return (b >= 'a' && b <= 'z') || (b >= 'A' && b <= 'Z') || b == '_';
  }
  for (size_t i = 0; i < n; i++) {
    if (!cn_str_byte_ok(pl_nat_byte_at(v, i)))
      return false;
  }
  return true;
}

char* pl_nat_to_cstr(const ax_allocator* loc, pl_val val) {
  if (!pl_is_nat(val) || !pl_nat_is_str(val))
    return NULL;
  size_t n = pl_nat_byte_len(val);
  char* s = ax_calloc(loc, char, n + 1);
  for (size_t i = 0; i < n; i++)
    s[i] = (char)pl_nat_byte_at(val, i);
  s[n] = '\0';
  return s;
}
