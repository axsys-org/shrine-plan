BUILD_TYPE ?= debug
PROFILE ?=
CC ?= cc
PREFIX ?= /usr/local
BUILD_PROFILE_SUFFIX := $(if $(PROFILE),-$(PROFILE),)
BUILD_DIR ?= build/$(BUILD_TYPE)$(BUILD_PROFILE_SUFFIX)
AR ?= ar
DOCKER ?= docker

NIX_DOCKER_IMAGE ?= nixos/nix@sha256:bf1d938835ab96312f098fa6c2e9cab367728e0aad0646ee3e02a787c80d8fb8
# TSan needs native execution: Rosetta's address space is incompatible with
# its shadow memory. Keep these lazy so ordinary builds never query Docker.
LINUX_PLATFORM ?= $(shell $(DOCKER) version --format '{{.Server.Os}}/{{.Server.Arch}}')
LINUX_PLATFORM_ID = $(subst /,-,$(LINUX_PLATFORM))
LINUX_NIX_VOLUME ?= enki-nix-2-34-7-$(LINUX_PLATFORM_ID)

VALID_BUILD_TYPES := debug release asan ubsan tsan coverage profile
VALID_BUILD_TYPES += pgo-generate pgo

PGO_CC ?= clang
LLVM_PROFDATA ?= llvm-profdata
PGO_DIR ?= build/pgo
PGO_GEN_BUILD_DIR ?= build/pgo-generate
PGO_USE_BUILD_DIR ?= $(PGO_DIR)
PGO_RUN_DIR ?= $(PGO_DIR)/run
PGO_RAW_DIR ?= $(PGO_DIR)/raw
PGO_PROFILE ?= $(PGO_DIR)/enki.profdata
PGO_PROFILE_PATTERN ?= $(CURDIR)/$(PGO_RAW_DIR)/wisp-%m.profraw
PGO_ASSEMBLER_PROFILE_PATTERN ?= $(CURDIR)/$(PGO_RAW_DIR)/assembler-%m.profraw
PGO_REAVER_SRC ?= $(CURDIR)/reaver/src
PGO_WORKLOAD ?= --file-root ./reaver/src ./reaver/src/plan reaver main

# Per-package include paths enforce the layering (axsys < plan < enki):
# compiling pkg/plan, the pkg/enki include directory is not on the path.
AXSYS_INC := -Ipkg/axsys/include
PLAN_INC := -Ipkg/plan/include $(AXSYS_INC)
ENKI_INC := -Ipkg/enki/include $(PLAN_INC)

BASE_CPPFLAGS := -Itests/support -Itests/property/vendor/theft $(NIX_CFLAGS_COMPILE)
BASE_CFLAGS := -std=c23 -MMD -MP -D_GNU_SOURCE -pthread

WARN_COMMON := -Wall -Wextra  \
	-Wpedantic -Wshadow -Wconversion -Wstrict-prototypes \
	-Wmissing-prototypes -Wold-style-definition -Wnull-dereference \
	-Wdouble-promotion -Werror \
	-Wno-sign-conversion -Wno-char-subscripts -Wno-unused-function

# Computed gotos (pl_run) are a GNU extension: clang has a targeted
# suppression; gcc only has the -Wpedantic bucket, handled by a
# GCC-only pragma in eval.c.
ifneq (,$(findstring clang,$(shell $(CC) --version 2>/dev/null)))
WARN_COMMON += -Wno-gnu-label-as-value
endif

WARN_CFLAGS = $(WARN_COMMON)

# Release hardening.  nix/mkenki.nix disables the stdenv's own fortify so this
# level-3 setting is the one in force (the -U avoids a redefinition warning).
# Measured 2026-09-15 on the plangrm bench: no cost against the same build
# without these flags, so they stay on for the perf build types too.
HARDEN_CFLAGS := -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3 -fstack-protector-strong

# Full LTO for the perf builds (release + final pgo): the evaluator's hot
# loop calls out-of-line builders (pl_bump, pl_mk_thke, ...) across TUs.
# profile (tracy) skips it for sane attribution; pgo-generate skips it
# because only the final instr-use build's codegen matters.
#
# Darwin-only for now: ld64 links bitcode archive members out of the
# box, but the Linux legs link with binutils ld.bfd, which chokes on
# bitcode archives ("archive has no index") — enabling LTO there needs
# llvm-ar + lld (llvmPackages.bintools) in the build environment first.
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
LTO_CFLAGS := -flto
HOST_LDFLAGS := -L/opt/homebrew/lib
else
LTO_CFLAGS :=
HOST_LDFLAGS :=
endif

BUILD_CFLAGS_debug := -O0 -g3 -DDEBUG
BUILD_CFLAGS_relbase := -O3 -DNDEBUG $(HARDEN_CFLAGS)
BUILD_CFLAGS_release := $(BUILD_CFLAGS_relbase) $(LTO_CFLAGS)
BUILD_CFLAGS_profile := $(BUILD_CFLAGS_relbase) -g3 -fno-omit-frame-pointer -fdebug-info-for-profiling
BUILD_CFLAGS_pgo-generate := $(BUILD_CFLAGS_relbase) -fprofile-instr-generate
BUILD_CFLAGS_pgo := $(BUILD_CFLAGS_relbase) $(LTO_CFLAGS) -fprofile-instr-use=$(PGO_PROFILE) -Wno-error=profile-instr-unprofiled
BUILD_CFLAGS_asan := -O1 -g3 -fsanitize=address -fno-omit-frame-pointer $(HARDEN_CFLAGS)
BUILD_CFLAGS_ubsan := -O1 -g3 -fsanitize=undefined -fno-omit-frame-pointer $(HARDEN_CFLAGS)
BUILD_CFLAGS_tsan := -O1 -g3 -fsanitize=thread -fno-omit-frame-pointer $(HARDEN_CFLAGS)
BUILD_CFLAGS_coverage := -O1 -g3 --coverage -Wno-pedantic $(HARDEN_CFLAGS)

BUILD_LDFLAGS_debug :=
BUILD_LDFLAGS_release := $(LTO_CFLAGS)
BUILD_LDFLAGS_profile :=
BUILD_LDFLAGS_pgo-generate := -fprofile-instr-generate
BUILD_LDFLAGS_pgo := $(LTO_CFLAGS) -fprofile-instr-use=$(PGO_PROFILE)
BUILD_LDFLAGS_asan := -fsanitize=address
BUILD_LDFLAGS_ubsan := -fsanitize=undefined
BUILD_LDFLAGS_tsan := -fsanitize=thread
BUILD_LDFLAGS_coverage := --coverage

ifeq ($(filter $(BUILD_TYPE),$(VALID_BUILD_TYPES)),)
$(error BUILD_TYPE must be one of $(VALID_BUILD_TYPES))
endif

# GC stress: every reserve collects (see pkg/plan/include/plan/heap.h)
# Every reserve collects, so the allocation-heavy eval suites run far past
# the default 60 s per-process test alarm (tests/support/test.h): widen it.
ifdef GC_STRESS
BASE_CFLAGS += -DPL_GC_STRESS -DENKI_TEST_TIMEOUT_SECONDS=900
endif

# Yield stress: every depth-0 safepoint suspends and resumes the thread
# (see pkg/plan/src/eval.c, spec §10.1)
ifdef YIELD_STRESS
BASE_CFLAGS += -DPL_YIELD_STRESS
endif

APP_DIR := pkg/enki/app
APP_SRCS := $(wildcard $(APP_DIR)/*.c)
APP_BINS := $(patsubst $(APP_DIR)/%.c,$(BUILD_DIR)/bin/%,$(APP_SRCS))

CPPFLAGS_ALL := $(BASE_CPPFLAGS) $(CPPFLAGS)
CFLAGS_ALL := $(BASE_CFLAGS) $(WARN_CFLAGS) $(BUILD_CFLAGS_$(BUILD_TYPE)) $(CFLAGS)
LDFLAGS_ALL := $(BUILD_LDFLAGS_$(BUILD_TYPE)) $(LDFLAGS) -pthread $(HOST_LDFLAGS) -lgmp -llmdb -lcrypto -lcurl -lsodium -lblake3 -lz

ifeq ($(PROFILE),tracy)
CPPFLAGS_ALL += -I/opt/homebrew/opt/tracy/include/tracy
CFLAGS_ALL += -DTRACY_ENABLE
LDFLAGS_ALL += -L/opt/homebrew/opt/tracy/lib -Wl,-rpath,/opt/homebrew/opt/tracy/lib -lTracyClient
endif

AXSYS_SRCS := $(wildcard pkg/axsys/src/*.c)
PLAN_SRCS := $(wildcard pkg/plan/src/*.c)
ENKI_SRCS := $(wildcard pkg/enki/src/*.c)
HEADERS := $(wildcard pkg/axsys/include/axsys/*.h) \
	$(wildcard pkg/plan/include/plan/*.h) \
	$(wildcard pkg/plan/src/*.h) \
	$(wildcard pkg/enki/include/enki/*.h)

UNIT_DIR := tests/unit
PROPERTY_DIR := tests/property
FUZZ_DIR := tests/fuzz
PERF_DIR := tests/perf
VENDOR_THEFT_DIR := tests/property/vendor/theft

TSAN_UNIT_SRCS := $(wildcard $(UNIT_DIR)/*_tsan.c)
UNIT_SRCS := $(filter-out $(TSAN_UNIT_SRCS),$(wildcard $(UNIT_DIR)/*.c))
PROPERTY_SRCS := $(wildcard $(PROPERTY_DIR)/*.c)
THEFT_SRCS := $(wildcard $(VENDOR_THEFT_DIR)/*.c)
FUZZ_SRCS := $(wildcard $(FUZZ_DIR)/*.c)
PERF_SRCS := $(wildcard $(PERF_DIR)/*.c)

AXSYS_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(AXSYS_SRCS))
PLAN_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(PLAN_SRCS))
ENKI_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(ENKI_SRCS))
LIB_OBJS := $(AXSYS_OBJS) $(PLAN_OBJS) $(ENKI_OBJS)

UNIT_BINS := $(patsubst %.c,$(BUILD_DIR)/%,$(UNIT_SRCS))
TSAN_UNIT_BINS := $(patsubst %.c,$(BUILD_DIR)/%,$(TSAN_UNIT_SRCS))
PROPERTY_BINS := $(patsubst %.c,$(BUILD_DIR)/%,$(PROPERTY_SRCS))
THEFT_OBJS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(THEFT_SRCS))
FUZZ_BINS := $(patsubst %.c,$(BUILD_DIR)/%,$(FUZZ_SRCS))
PERF_BINS := $(patsubst %.c,$(BUILD_DIR)/%,$(PERF_SRCS))

LIB_AXSYS := $(BUILD_DIR)/lib/libaxsys.a
LIB_PLAN := $(BUILD_DIR)/lib/libplan.a
LIB_ENKI := $(BUILD_DIR)/lib/libenki.a
LIBS := $(LIB_AXSYS) $(LIB_PLAN) $(LIB_ENKI)

ifeq ($(BUILD_TYPE),tsan)
ACTIVE_UNIT_BINS := $(UNIT_BINS) $(TSAN_UNIT_BINS)
else
ACTIVE_UNIT_BINS := $(UNIT_BINS)
endif

# Booting the assembler with a collection at every reserve takes hours, not
# minutes: GC_STRESS runs skip the CLI suite (the plan-level suites already
# drive the collector through every evaluator path).
ifdef GC_STRESS
ACTIVE_UNIT_BINS := $(filter-out $(BUILD_DIR)/tests/unit/test_wisp_cli,$(ACTIVE_UNIT_BINS))
endif

ifeq ($(BUILD_TYPE),pgo)
PGO_PROFILE_TARGETS := $(LIB_OBJS) $(THEFT_OBJS) $(APP_BINS) $(UNIT_BINS) \
	$(TSAN_UNIT_BINS) $(PROPERTY_BINS) $(FUZZ_BINS) $(PERF_BINS)
$(PGO_PROFILE_TARGETS): $(PGO_PROFILE)
$(PGO_PROFILE):
	$(MAKE) pgo-profile
endif

TIDY_FILES := $(AXSYS_SRCS) $(PLAN_SRCS) $(ENKI_SRCS) $(UNIT_SRCS) $(PROPERTY_SRCS) $(FUZZ_SRCS) $(TSAN_UNIT_SRCS)
TIDY_FILES_ABS := $(addprefix $(CURDIR)/,$(TIDY_FILES))

FORMAT_FILES := $(HEADERS) $(AXSYS_SRCS) $(PLAN_SRCS) $(ENKI_SRCS) $(APP_SRCS) \
	$(UNIT_SRCS) $(TSAN_UNIT_SRCS) $(PROPERTY_SRCS) $(FUZZ_SRCS) \
	$(VENDOR_THEFT_DIR)/theft.h $(VENDOR_THEFT_DIR)/theft.c \
	tests/support/fff.h tests/support/test.h tests/support/test_plan.h \
	tests/support/test_http_server.h

FUZZ_CFLAGS := -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer
FUZZ_ARGS ?= $(FUZZ_DIR)/corpus -max_total_time=10

LCOV_INFO := $(BUILD_DIR)/coverage/enki.info
LCOV_FILTERED_INFO := $(BUILD_DIR)/coverage/enki.filtered.info
LCOV_NORMALIZED_INFO := $(BUILD_DIR)/coverage/enki.normalized.info
COVERAGE_HTML_DIR := $(BUILD_DIR)/html
LCOV_IGNORE_ERRORS ?= --ignore-errors inconsistent,inconsistent,mismatch,mismatch,gcov,gcov,unused,unused

LCOV_NORMALIZE_AWK = function emit(tag, count, i) { printf "%s%s", tag, field[1]; for (i = 2; i <= count; i++) printf ",%s", field[i]; printf "\n" } /^SF:/ { prefix = "SF:" source_root "/"; if (index($$0, prefix) == 1) print "SF:" substr($$0, length(prefix) + 1); else print; next } /^DA:/ { count = split(substr($$0, 4), field, ","); field[2] = field[2] == "0" ? "0" : "1"; emit("DA:", count); next } /^FNA:/ { count = split(substr($$0, 5), field, ","); field[2] = field[2] == "0" ? "0" : "1"; emit("FNA:", count); next } /^BRDA:/ { count = split(substr($$0, 6), field, ","); if (field[4] != "-") field[4] = field[4] == "0" ? "0" : "1"; emit("BRDA:", count); next } { print }
LCOV_NORMALIZE_HTML_AWK = function replace(line, position) { while ((position = index(line, source_root)) != 0) line = substr(line, 1, position - 1) "." substr(line, position + length(source_root)); return line } { print replace($$0) }

.PHONY: all lib bin install test test-binaries test-unit test-property fuzz fuzz-bin perf-binaries pgo \
	pgo-profile coverage tidy check-layering format format-check compile-commands nix-ci linux-check \
	linux-shell clean distclean

all: lib bin

nix-ci:
	./tools/nix-ci

linux-check:
	@$(DOCKER) volume create $(LINUX_NIX_VOLUME) >/dev/null
	$(DOCKER) run --rm --platform $(LINUX_PLATFORM) \
		--volume $(LINUX_NIX_VOLUME):/nix \
		--volume $(CURDIR):/source:ro \
		--env 'NIX_CONFIG=filter-syscalls = false' \
		--workdir / \
		$(NIX_DOCKER_IMAGE) \
		/bin/sh /source/tools/linux-check

linux-shell:
	@$(DOCKER) volume create $(LINUX_NIX_VOLUME) >/dev/null
	$(DOCKER) run --rm --interactive --tty --platform $(LINUX_PLATFORM) \
		--volume $(LINUX_NIX_VOLUME):/nix \
		--volume $(CURDIR):/src \
		--env 'NIX_CONFIG=filter-syscalls = false' \
		--workdir /src \
		$(NIX_DOCKER_IMAGE) \
		nix --extra-experimental-features 'nix-command flakes' develop path:/src

bin: $(APP_BINS)

$(BUILD_DIR)/bin/%: $(APP_DIR)/%.c $(LIBS)
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(CFLAGS_ALL) $< $(LIB_ENKI) $(LIB_PLAN) $(LIB_AXSYS) $(LDFLAGS_ALL) -o $@

lib: $(LIBS)

# Recreate archives instead of updating them in place: `ar r` keeps members
# for sources that no longer exist, and a stale member from another branch
# then fails the link (or silently shadows a symbol).

$(LIB_AXSYS): $(AXSYS_OBJS)
	@mkdir -p $(dir $@)
	rm -f $@ && $(AR) rcs $@ $^

$(LIB_PLAN): $(PLAN_OBJS)
	@mkdir -p $(dir $@)
	rm -f $@ && $(AR) rcs $@ $^

$(LIB_ENKI): $(ENKI_OBJS)
	@mkdir -p $(dir $@)
	rm -f $@ && $(AR) rcs $@ $^

# Layered compile rules (R1-R3): each package sees only its own include
# path and the layers beneath it.
$(BUILD_DIR)/pkg/axsys/%.o: pkg/axsys/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(AXSYS_INC) $(CFLAGS_ALL) -c $< -o $@

$(BUILD_DIR)/pkg/plan/%.o: pkg/plan/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(PLAN_INC) -Ipkg/plan/src $(CFLAGS_ALL) -c $< -o $@

$(BUILD_DIR)/pkg/enki/%.o: pkg/enki/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(CFLAGS_ALL) -c $< -o $@

$(BUILD_DIR)/tests/%.o: tests/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(CFLAGS_ALL) -c $< -o $@

$(BUILD_DIR)/tests/unit/%: tests/unit/%.c tests/support/test.h \
		tests/support/greatest.h $(LIBS)
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(CFLAGS_ALL) $< $(LIB_ENKI) $(LIB_PLAN) $(LIB_AXSYS) $(LDFLAGS_ALL) -o $@

$(BUILD_DIR)/tests/property/%: tests/property/%.c $(LIBS) $(THEFT_OBJS)
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(CFLAGS_ALL) $< $(LIB_ENKI) $(LIB_PLAN) $(LIB_AXSYS) $(THEFT_OBJS) \
		$(LDFLAGS_ALL) -o $@

$(BUILD_DIR)/tests/fuzz/%: tests/fuzz/%.c $(LIBS)
	@if ! $(CC) --version 2>/dev/null | grep -qi clang; then \
		echo "libFuzzer target requires Clang; use CC=clang"; \
		exit 2; \
	fi
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(BASE_CFLAGS) $(WARN_CFLAGS) $(BUILD_CFLAGS_asan) \
		$(FUZZ_CFLAGS) $< $(LIB_ENKI) $(LIB_PLAN) $(LIB_AXSYS) $(LDFLAGS_ALL) -o $@

$(BUILD_DIR)/tests/perf/%: tests/perf/%.c $(LIBS)
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS_ALL) $(ENKI_INC) $(CFLAGS_ALL) $< $(LIB_ENKI) $(LIB_PLAN) $(LIB_AXSYS) $(LDFLAGS_ALL) -o $@

install: lib bin
	install -d $(PREFIX)/lib $(PREFIX)/include/axsys $(PREFIX)/include/plan $(PREFIX)/include/enki
	install -m 0644 $(LIB_AXSYS) $(PREFIX)/lib/libaxsys.a
	install -m 0644 $(LIB_PLAN) $(PREFIX)/lib/libplan.a
	install -m 0644 $(LIB_ENKI) $(PREFIX)/lib/libenki.a
	install -m 0644 pkg/axsys/include/axsys/*.h $(PREFIX)/include/axsys/
	install -m 0644 pkg/plan/include/plan/*.h $(PREFIX)/include/plan/
	install -m 0644 pkg/enki/include/enki/*.h $(PREFIX)/include/enki/
	install -d $(PREFIX)/bin
	install -m 0755 $(APP_BINS) $(PREFIX)/bin/

test-binaries: $(ACTIVE_UNIT_BINS) $(PROPERTY_BINS)

test: check-layering test-unit test-property

test-unit: $(ACTIVE_UNIT_BINS) $(APP_BINS)
	@set -eu; for test_bin in $(ACTIVE_UNIT_BINS); do \
		ENKI_WISP_BIN=$(CURDIR)/$(BUILD_DIR)/bin/wisp "$$test_bin"; \
	done

test-property: $(PROPERTY_BINS)
	@set -eu; for test_bin in $(PROPERTY_BINS); do "$$test_bin"; done

# Layering check (R1-R3): grep #include lines against the dependency
# matrix.  axsys must not include plan/ or enki/; plan must not include
# enki/.
check-layering:
	@status=0; \
	if grep -rnE '#include\s+["<](plan|enki)/' pkg/axsys --include='*.c' --include='*.h' 2>/dev/null; then \
		echo "layering violation: pkg/axsys includes plan/ or enki/ headers"; status=1; \
	fi; \
	if grep -rnE '#include\s+["<]enki/' pkg/plan --include='*.c' --include='*.h' 2>/dev/null; then \
		echo "layering violation: pkg/plan includes enki/ headers"; status=1; \
	fi; \
	if [ $$status -eq 0 ]; then echo "check-layering: OK"; fi; \
	exit $$status

fuzz-bin: $(FUZZ_BINS)

fuzz: $(FUZZ_BINS)
	@set -eu; for fuzz_bin in $(FUZZ_BINS); do "$$fuzz_bin" $(FUZZ_ARGS); done

perf-binaries: $(PERF_BINS)

pgo: pgo-profile
	$(MAKE) BUILD_TYPE=pgo BUILD_DIR=$(PGO_USE_BUILD_DIR) CC=$(PGO_CC) bin

pgo-profile:
	@mkdir -p $(PGO_RAW_DIR) $(dir $(PGO_PROFILE)) $(PGO_RUN_DIR)/reaver $(PGO_DIR)/reaver
	@rm -f $(PGO_RAW_DIR)/*.profraw $(PGO_PROFILE)
	@rm -rf $(PGO_RUN_DIR)/snap $(PGO_RUN_DIR)/reaver/src $(PGO_DIR)/reaver/src
	@ln -s $(PGO_REAVER_SRC) $(PGO_RUN_DIR)/reaver/src
	@ln -s $(PGO_REAVER_SRC) $(PGO_DIR)/reaver/src
	$(MAKE) BUILD_TYPE=pgo-generate BUILD_DIR=$(PGO_GEN_BUILD_DIR) CC=$(PGO_CC) bin
	cd $(PGO_RUN_DIR) && LLVM_PROFILE_FILE="$(PGO_PROFILE_PATTERN)" $(CURDIR)/$(PGO_GEN_BUILD_DIR)/bin/wisp $(PGO_WORKLOAD)
	cd $(PGO_RUN_DIR) && LLVM_PROFILE_FILE="$(PGO_ASSEMBLER_PROFILE_PATTERN)" $(CURDIR)/$(PGO_GEN_BUILD_DIR)/bin/assembler </dev/null >/dev/null
	$(LLVM_PROFDATA) merge -output=$(PGO_PROFILE) $(PGO_RAW_DIR)/*.profraw

coverage:
	$(MAKE) BUILD_TYPE=coverage test
	@mkdir -p $(BUILD_DIR)/coverage $(COVERAGE_HTML_DIR)
	lcov --capture --directory $(BUILD_DIR) --output-file $(LCOV_INFO) $(LCOV_IGNORE_ERRORS)
	lcov --remove $(LCOV_INFO) '*/tests/*' '*/nix/store/*' --output-file $(LCOV_FILTERED_INFO) \
		$(LCOV_IGNORE_ERRORS)
	awk -v 'source_root=$(CURDIR)' '$(LCOV_NORMALIZE_AWK)' $(LCOV_FILTERED_INFO) > $(LCOV_NORMALIZED_INFO)
	mv $(LCOV_NORMALIZED_INFO) $(LCOV_FILTERED_INFO)
	genhtml $(LCOV_FILTERED_INFO) --output-directory $(COVERAGE_HTML_DIR)
	find $(COVERAGE_HTML_DIR) -type f -name '*.html' -exec sh -c 'root=$$1; program=$$2; shift 2; for file; do awk -v "source_root=$$root" "$$program" "$$file" > "$$file.tmp"; mv "$$file.tmp" "$$file"; done' sh "$(CURDIR)" '$(LCOV_NORMALIZE_HTML_AWK)' {} +

# clang-tidy needs a compilation database: bear (in the devShell) records a
# forced rebuild of the current BUILD_TYPE, libraries, apps and test binaries.
compile-commands:
	bear --output compile_commands.json -- $(MAKE) -B BUILD_TYPE=$(BUILD_TYPE) lib bin test-binaries

tidy:
	@test -f compile_commands.json || \
		{ echo "compile_commands.json missing; run make compile-commands first"; exit 2; }
	clang-tidy --quiet -p . $(TIDY_FILES_ABS) --warnings-as-errors='*'

format:
	clang-format -i $(FORMAT_FILES)
	@if command -v treefmt >/dev/null 2>&1; then treefmt; fi

format-check:
	clang-format --dry-run --Werror $(FORMAT_FILES)
	@if command -v treefmt >/dev/null 2>&1; then treefmt --fail-on-change; fi

clean:
	rm -rf $(BUILD_DIR)

distclean:
	rm -rf build compile_commands.json result result-*

-include $(LIB_OBJS:.o=.d)
-include $(THEFT_OBJS:.o=.d)
# The single-step compile-and-link rules emit <binary>.d beside each binary;
# without these includes a header edit leaves stale test and app binaries.
-include $(UNIT_BINS:=.d) $(TSAN_UNIT_BINS:=.d) $(PROPERTY_BINS:=.d)
-include $(APP_BINS:=.d) $(PERF_BINS:=.d) $(FUZZ_BINS:=.d)
