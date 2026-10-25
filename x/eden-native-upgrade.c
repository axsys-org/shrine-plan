/* Trusted bootstrap upgrade through the existing native store API.
 * Silo transports compiler code only; application state stays in its arena.
 * The namespace hash must match before a new continuation is committed. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "axsys/ds.h"
#include "plan/build.h"
#include "plan/eval.h"
#include "plan/heap.h"
#include "plan/nat.h"
#include "plan/store.h"
#include "plan/value.h"

typedef struct entry {
  pl_val key, value;
} entry;
static entry* memo;
static pl_store* destination;
static pl_thread* thread;
static pl_val replacement;
static unsigned replacements;
static pl_val publisher_before, publisher_after;
static unsigned publisher_replacements;
static bool publication_pass;

static int fail(const char* message) {
  fprintf(stderr, "Eden upgrade: %s\n", message);
  return 1;
}
static bool text_is(pl_val value, const char* text) {
  if (!pl_is_nat(value) || pl_nat_byte_len(value) != strlen(text))
    return false;
  for (size_t i = 0; i < strlen(text); i++)
    if (pl_nat_byte_at(value, i) != (uint8_t)text[i])
      return false;
  return true;
}
static pl_val body(pl_val value) {
  return pl_tag(value) == PL_TAG_PIN ? pl_pin_body(pl_ptr(value)) : value;
}
static bool bootstrap_module(pl_val value) {
  pl_val object = body(value);
  return pl_tag(object) == PL_TAG_APP && pl_app_n(pl_ptr(object)) == 6 &&
         text_is(pl_app_head(pl_ptr(object)), "/foil/artifact/v3perc") &&
         text_is(pl_app_args(pl_ptr(object))[3], "eden_store");
}
/* These are immutable compiler evidence, including the compiler identity pin.
 * A bootstrap law update must not rewrite their captured import contexts. */
static bool compiler_evidence(pl_val value) {
  pl_val object = body(value);
  if (pl_tag(object) != PL_TAG_APP)
    return false;
  pl_val tag = pl_app_head(pl_ptr(object));
  return text_is(tag, "/foil/artifact/v3perc") ||
         text_is(tag, "foil/compiled-publication/v2") ||
         text_is(tag, "foil/prepared-publication/v2") ||
         text_is(tag, "foil/context/v2") ||
         text_is(tag, "foil/system-build/v1");
}
static pl_val stable(pl_val value) {
  return pl_store_snapshot_normal(thread, pl_nf(thread, value));
}
static pl_val copy(pl_val value, bool rewrite) {
  if (pl_is_nat63(value) || (!rewrite && pl_store_owns(destination, value)))
    return value;
  ptrdiff_t at = ax_hmgeti(memo, value);
  if (at >= 0)
    return memo[at].value;
  if (rewrite && publication_pass && value == publisher_before) {
    publisher_replacements++;
    ax_hmput(memo, value, publisher_after);
    return publisher_after;
  }
  if (rewrite && !publication_pass && bootstrap_module(value)) {
    pl_val next = pl_tag(value) == PL_TAG_PIN ? replacement : body(replacement);
    replacements++;
    ax_hmput(memo, value, next);
    return next;
  }
  if (rewrite && publication_pass && compiler_evidence(value)) {
    ax_hmput(memo, value, value);
    return value;
  }
  pl_val next = value;
  if (pl_is_nat(value)) {
    if (rewrite)
      return value;
    size_t count = pl_nat_limb_len(value);
    uint64_t* limbs;
    pl_gc_reserve(thread, count + 1);
    next = pl_mk_nat_limbs(thread, count, &limbs);
    for (size_t i = 0; i < count; i++)
      limbs[i] = pl_nat_limb_at(value, i);
    next = stable(next);
  } else if (pl_tag(value) == PL_TAG_PIN) {
    pl_val before = body(value), after = copy(before, rewrite);
    if (!rewrite || before != after) {
      pl_gc_reserve(thread, 16);
      next = stable(pl_pin(thread, after));
    }
  } else if (pl_tag(value) == PL_TAG_LAW) {
    pl_cell* law = pl_ptr(value);
    pl_val name = copy(pl_law_name(law), rewrite);
    pl_val definition = copy(pl_law_body(law), rewrite);
    if (!rewrite || name != pl_law_name(law) ||
        definition != pl_law_body(law)) {
      pl_gc_reserve(thread, 8);
      next = stable(pl_mk_law(thread, pl_law_arity(law), name, definition));
    }
  } else if (pl_tag(value) == PL_TAG_APP) {
    pl_cell* app = pl_ptr(value);
    uint32_t count = pl_app_n(app);
    pl_val head = copy(pl_app_head(app), rewrite);
    pl_val* args = malloc((size_t)count * sizeof(*args));
    if (args == NULL) {
      fail("out of memory");
      exit(1);
    }
    bool changed = head != pl_app_head(app);
    for (uint32_t i = 0; i < count; i++) {
      args[i] = copy(pl_app_args(app)[i], rewrite);
      changed |= args[i] != pl_app_args(app)[i];
    }
    if (!rewrite || changed) {
      pl_gc_reserve(thread, count + 3);
      next = stable(pl_mk_app_from(thread, head, count, args));
    }
    free(args);
  } else {
    fail("unexpected non-normal value");
    exit(1);
  }
  ax_hmput(memo, value, next);
  return next;
}
static pl_val find_module(pl_val value) {
  if (pl_is_nat(value) || ax_hmgeti(memo, value) >= 0)
    return 0;
  ax_hmput(memo, value, value);
  if (bootstrap_module(value))
    return value;
  if (pl_tag(value) == PL_TAG_PIN)
    return find_module(body(value));
  for (uint32_t i = 0; i < pl_nf_nfields(value); i++) {
    pl_val found = find_module(pl_nf_field(value, i));
    if (found != 0)
      return found;
  }
  return 0;
}

/* Only the bootstrap's mount-publication law is replaceable. Captured
 * operation laws inside the retained namespace are never traversed. */
static pl_val find_publisher(pl_val value, unsigned* count) {
  if (pl_is_nat(value) || compiler_evidence(value) || ax_hmgeti(memo, value) >= 0)
    return 0;
  ax_hmput(memo, value, value);
  if (pl_tag(value) == PL_TAG_LAW &&
      text_is(pl_law_name(pl_ptr(value)), "publish-mount")) {
    (*count)++;
    return value;
  }
  pl_val found = 0;
  if (pl_tag(value) == PL_TAG_PIN)
    return find_publisher(body(value), count);
  for (uint32_t i = 0; i < pl_nf_nfields(value); i++) {
    pl_val next = find_publisher(pl_nf_field(value, i), count);
    if (next != 0)
      found = next;
  }
  return found;
}

int main(int argc, char** argv) {
  if (argc != 4 ||
      (strcmp(argv[1], "export-code") && strcmp(argv[1], "upgrade"))) {
    fprintf(stderr,
            "Usage: eden-native-upgrade export-code NATIVE-CODE SILO-CODE\n"
            "       eden-native-upgrade upgrade SILO-CODE NATIVE-WORLD\n");
    return 2;
  }
  bool exporting = !strcmp(argv[1], "export-code");
  char error[512] = {0};
  pl_store* source = exporting
                         ? pl_store_new_native_ro(argv[2], error, sizeof(error))
                         : pl_store_new_silo_ro(argv[2], (size_t)1 << 30);
  if (source == NULL)
    return fail("cannot open compiler artifact");
  pl_heap* source_heap = pl_heap_new((size_t)1 << 20, source);
  pl_thread* source_thread = pl_thread_new(source_heap);
  uint8_t hash[32];
  if (!pl_store_get_root(source, hash))
    return fail("compiler artifact has no root");
  pl_val code = pl_store_load(source_thread, hash), object = body(code);
  bool publication_upgrade = pl_tag(object) == PL_TAG_APP &&
      pl_app_n(pl_ptr(object)) == 2 &&
      text_is(pl_app_head(pl_ptr(object)), "eden-bootstrap-upgrade/v2");
  if (pl_tag(object) != PL_TAG_APP ||
      !(publication_upgrade || (pl_app_n(pl_ptr(object)) == 1 &&
        text_is(pl_app_head(pl_ptr(object)), "eden-bootstrap-upgrade/v1"))) ||
      pl_tag(pl_app_args(pl_ptr(object))[0]) != PL_TAG_PIN)
    return fail("not a prepared bootstrap compiler artifact");

  destination = exporting ? pl_store_new_silo(argv[3], (size_t)1 << 30)
                          : pl_store_new_native(argv[3], error, sizeof(error));
  if (destination == NULL)
    return fail("cannot open destination; stop its writer first");
  pl_heap* heap = pl_heap_new((size_t)1 << 20, destination);
  thread = pl_thread_new(heap);
  thread->rplan_f = true;
  code = copy(code, false);
  ax_hmfree(memo);
  if (exporting) {
    if (!pl_store_save_root(destination, code, hash, error, sizeof(error)))
      return fail(error);
    return 0;
  }

  if (!pl_store_get_root(destination, hash))
    return fail("world has no continuation");
  pl_val root = body(pl_store_load(thread, hash));
  if (pl_tag(root) != PL_TAG_APP ||
      pl_tag(pl_app_head(pl_ptr(root))) != PL_TAG_LAW ||
      !text_is(pl_law_name(pl_ptr(pl_app_head(pl_ptr(root)))), "resume") ||
      (pl_app_n(pl_ptr(root)) != 2 && pl_app_n(pl_ptr(root)) != 3))
    return fail("unsupported continuation; existing root retained");
  uint32_t count = pl_app_n(pl_ptr(root));
  pl_val state = body(pl_app_args(pl_ptr(root))[count - 1]);
  pl_val service = pl_app_args(pl_ptr(root))[count - 2];
  pl_val old = find_module(service);
  ax_hmfree(memo);
  if (old == 0)
    return fail("bootstrap module missing; existing root retained");
  if (!pl_store_save_pin(destination, code, hash, error, sizeof(error)))
    return fail(error);
  code = pl_store_load(thread, hash);
  pl_val factory = pl_app_args(pl_ptr(body(code)))[0];
  pl_gc_reserve(thread, 16);
  pl_val argument =
      pl_tag(old) == PL_TAG_PIN ? old : stable(pl_pin(thread, old));
  pl_val result = stable(pl_apply(thread, body(factory), argument));
  if (pl_tag(result) != PL_TAG_APP || pl_app_head(pl_ptr(result)) != 0 ||
      pl_app_n(pl_ptr(result)) != 1)
    return fail(
        "bootstrap compilation refused the update; existing root retained");
  pl_val compiled = pl_app_args(pl_ptr(result))[0];
  if (pl_tag(compiled) != PL_TAG_APP || pl_app_n(pl_ptr(compiled)) != 2)
    return fail("invalid compiler result; existing root retained");
  pl_val constructor = pl_app_args(pl_ptr(compiled))[0];
  replacement = pl_app_args(pl_ptr(compiled))[1];
  if (pl_tag(constructor) != PL_TAG_PIN || !bootstrap_module(replacement))
    return fail("invalid bootstrap replacement; existing root retained");
  if (publication_upgrade) {
    unsigned old_count = 0, new_count = 0;
    publisher_before = find_publisher(service, &old_count);
    ax_hmfree(memo);
    publisher_after = find_publisher(pl_app_args(pl_ptr(body(code)))[1], &new_count);
    ax_hmfree(memo);
    fprintf(stderr, "Publisher candidates: old=%u new=%u arity=%u/%u\n",
      old_count, new_count,
      publisher_before ? pl_law_arity(pl_ptr(publisher_before)) : 0,
      publisher_after ? pl_law_arity(pl_ptr(publisher_after)) : 0);
    if (old_count != 1 || new_count != 1 ||
        pl_law_arity(pl_ptr(publisher_before)) !=
          pl_law_arity(pl_ptr(publisher_after)))
      return fail("mount publisher closure ABI differs; existing root retained");
  }
  pl_val updated = copy(service, true);
  ax_hmfree(memo);
  if (replacements != 1)
    return fail("ambiguous bootstrap module; existing root retained");
  if (publication_upgrade) {
    unsigned count = 0;
    publisher_before = find_publisher(updated, &count);
    ax_hmfree(memo);
    if (count != 1)
      return fail("ambiguous mount publisher; existing root retained");
    publication_pass = true;
    updated = copy(updated, true);
    ax_hmfree(memo);
    if (publisher_replacements != 1)
      return fail("mount publisher was not replaced; existing root retained");
  }
  pl_val partial = pl_apply(thread, body(constructor), updated);
  pl_val prepared = stable(pl_apply(thread, partial, state));
  if (pl_tag(prepared) != PL_TAG_APP || pl_app_n(pl_ptr(prepared)) != 2)
    return fail("invalid continuation preparation; existing root retained");
  pl_val next = pl_app_args(pl_ptr(prepared))[0];
  pl_val retained = pl_app_args(pl_ptr(prepared))[1];
  if (pl_tag(next) != PL_TAG_PIN || pl_tag(retained) != PL_TAG_PIN ||
      pl_tag(body(next)) != PL_TAG_APP || pl_app_n(pl_ptr(body(next))) != 3 ||
      pl_app_args(pl_ptr(body(next)))[2] != retained)
    return fail("invalid retained namespace; existing root retained");
  pl_gc_reserve(thread, 16);
  pl_val before = stable(pl_pin(thread, state));
  uint8_t before_hash[32], after_hash[32];
  if (!pl_store_save_pin(destination, before, before_hash, error,
                         sizeof(error)) ||
      !pl_store_save_pin(destination, retained, after_hash, error,
                         sizeof(error)))
    return fail(error);
  if (memcmp(before_hash, after_hash, sizeof(before_hash)))
    return fail("namespace content changed; existing root retained");
  if (!pl_store_save_root(destination, next, hash, error, sizeof(error)))
    return fail(error);
  puts("Eden bootstrap upgraded; complete namespace content hash unchanged.");
  return 0;
}
