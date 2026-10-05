#include "test.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#ifndef ENKI_WISP_BIN
#define ENKI_WISP_BIN "wisp"
#endif

#ifndef ENKI_REAVER_PLAN_DIR
#define ENKI_REAVER_PLAN_DIR "./reaver/src/plan"
#endif

static const char* reaver_plan_dir(void) {
  const char* env_c = getenv("ENKI_REAVER_PLAN_DIR");
  return env_c != NULL && env_c[0] != '\0' ? env_c : ENKI_REAVER_PLAN_DIR;
}

static void reaver_src_dir(char* out, size_t out_cap) {
  const char* env_c = getenv("ENKI_REAVER_SRC_DIR");
  if (env_c != NULL && env_c[0] != '\0') {
    int s = snprintf(out, out_cap, "%s", env_c);
    ASSERT(s >= 0 && (size_t)s < out_cap, "ENKI_REAVER_SRC_DIR too long");
    return;
  }

  char cwd[2048];
  ASSERT_NOT_NULL(getcwd(cwd, sizeof(cwd)), "failed to get cwd");
  int s = snprintf(out, out_cap, "%s/reaver/src", cwd);
  ASSERT(s >= 0 && (size_t)s < out_cap, "reaver src path too long");
}

static const char* wisp_bin(void) {
  const char* env_c = getenv("ENKI_WISP_BIN");
  return env_c != NULL && env_c[0] != '\0' ? env_c : ENKI_WISP_BIN;
}

TEST(wisp_cli, reaver_module_exits_zero) {
  char command_c[4096];
  int command_s = snprintf(command_c, sizeof(command_c), "%s %s reaver",
                           wisp_bin(), reaver_plan_dir());

  ASSERT(command_s >= 0 && (size_t)command_s < sizeof(command_c),
         "failed to build wisp command");

  int status = system(command_c);

  ASSERT_NEQ(status, -1, "failed to run `%s`", command_c);
  ASSERT(WIFEXITED(status), "`%s` did not exit normally: status=%d", command_c,
         status);
  ASSERT_EQ(WEXITSTATUS(status), 0, "`%s` exited with %d", command_c,
            WEXITSTATUS(status));
}

/*
 * Save / snapshot round trip, the same flow as the reference x/reaver
 * driver (PlanAssembler.hs): assemble a module in BPLAN mode that pins a
 * program and calls Save, then resume from the snapshot directory in
 * RPLAN mode and run the bound program.
 */

static int run_cmd(const char* cmd, char* out, size_t out_cap) {
  FILE* p = popen(cmd, "r");
  if (p == NULL)
    return -1;
  size_t n = 0;
  int ch;
  while ((ch = fgetc(p)) != EOF && n + 1 < out_cap)
    out[n++] = (char)ch;
  out[n] = '\0';
  return pclose(p);
}

static bool file_contains(const char* path, const char* needle) {
  FILE* f = fopen(path, "r");
  ASSERT_NOT_NULL(f, "failed to open `%s`", path);

  bool found = false;
  size_t needle_n = strlen(needle);
  size_t matched = 0;
  int ch;
  while ((ch = fgetc(f)) != EOF) {
    if ((char)ch == needle[matched]) {
      matched++;
      if (matched == needle_n) {
        found = true;
        break;
      }
    } else {
      matched = (char)ch == needle[0] ? 1u : 0u;
    }
  }
  fclose(f);
  return found;
}

TEST(wisp_cli, save_silo_snapshot_round_trip) {
  char dir[] = "/tmp/enki-snaptest-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir), "failed to make temp dir");

  char path[512];
  (void)snprintf(path, sizeof(path), "%s/save1.plan", dir);
  FILE* f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  /* Print writes the raw bytes of a plain string nat (op 82, RPLAN). */
  fprintf(f,
          "(#bind Print\n"
          "  (#pin (#law \"Print\" (Print x) ((#pin \"R\") (\"Print\" x)))))\n"
          "(#bind Pin (#pin (#law \"Pin\" (Pin x) ((#pin \"B\") (\"Pin\" "
          "x)))))\n"
          "(#bind Save (#pin (#law \"Save\" (Save x) ((#pin \"B\") (\"Save\" "
          "x)))))\n"
          "(#bind prog\n"
          "  (#pin (#law \"prog\" (prog args) ((#pin \"R\") (\"Print\" "
          "\"snap-ok\")))))\n"
          "(Save prog)\n");
  fclose(f);

  char cmd[1024];
  char out[256];

  /* BPLAN assemble: pins prog, Save publishes it as the Silo root. */
  (void)snprintf(cmd, sizeof(cmd), "cd %s && %s %s save1 >/dev/null 2>&1", dir,
                 wisp_bin(), dir);
  int st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "assemble failed");

  (void)snprintf(path, sizeof(path), "%s/snap/pins.pack", dir);
  ASSERT_EQ(access(path, F_OK), 0, "snap/pins.pack not written");

  /* RPLAN resume: run the saved program, which prints "snap-ok" */
  (void)snprintf(cmd, sizeof(cmd), "cd %s && %s snap root _ 2>/dev/null", dir,
                 wisp_bin());
  st = run_cmd(cmd, out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "resume failed");
  ASSERT_NOT_NULL(strstr(out, "snap-ok"),
                  "resumed program did not print; got `%s`", out);
}

TEST(wisp_cli, save_text_hash_snapshot_round_trip) {
  char dir[] = "/tmp/enki-text-snaptest-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir), "failed to make temp dir");

  char path[512];
  (void)snprintf(path, sizeof(path), "%s/save1.plan", dir);
  FILE* f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  fprintf(f,
          "(#bind Print\n"
          "  (#pin (#law \"Print\" (Print x) ((#pin \"R\") (\"Print\" x)))))\n"
          "(#bind Save (#pin (#law \"Save\" (Save x) ((#pin \"B\") (\"Save\" "
          "x)))))\n"
          "(#bind prog\n"
          "  (#pin (#law \"prog\" (prog args) ((#pin \"R\") (\"Print\" "
          "\"text-ok\")))))\n"
          "(Save prog)\n");
  fclose(f);

  char cmd[1024];
  char out[256];
  (void)snprintf(cmd, sizeof(cmd),
                 "cd %s && %s --text-hash %s save1 >/dev/null 2>&1", dir,
                 wisp_bin(), dir);
  int st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "assemble failed");

  (void)snprintf(path, sizeof(path), "%s/snap/root.plan", dir);
  ASSERT_EQ(access(path, F_OK), 0, "snap/root.plan not written");

  (void)snprintf(cmd, sizeof(cmd),
                 "cd %s && %s --text-hash snap root _ 2>/dev/null", dir,
                 wisp_bin());
  st = run_cmd(cmd, out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "resume failed");
  ASSERT_NOT_NULL(strstr(out, "text-ok"),
                  "resumed program did not print; got `%s`", out);
}

TEST(wisp_cli, rplan_op_rejected_in_bplan) {
  char dir[] = "/tmp/enki-bplan-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));

  char path[512];
  (void)snprintf(path, sizeof(path), "%s/bad.plan", dir);
  FILE* f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  /* calling an op-82 (rplan) op at top level in BPLAN mode must fail */
  fprintf(f, "((#pin \"R\") (\"Print\" \"nope\"))\n");
  fclose(f);

  char cmd[1024];
  (void)snprintf(cmd, sizeof(cmd), "%s %s bad >/dev/null 2>&1", wisp_bin(),
                 dir);
  int st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) != 0,
         "RPLAN op should be rejected outside RPLAN mode");
}

TEST(wisp_cli, profile_json_accepts_both_flag_spellings) {
  char dir[] = "/tmp/enki-profile-cli-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));

  char module_path[512];
  (void)snprintf(module_path, sizeof(module_path), "%s/ok.plan", dir);
  FILE* f = fopen(module_path, "w");
  ASSERT_NOT_NULL(f);
  fputs("0\n", f);
  fclose(f);

  char trace_path[512];
  char cmd[2048];
  for (int equals = 0; equals < 2; equals++) {
    (void)snprintf(trace_path, sizeof(trace_path), "%s/trace-%d.json", dir,
                   equals);
    if (equals) {
      (void)snprintf(cmd, sizeof(cmd),
                     "%s --profile-json=%s %s ok >/dev/null 2>&1", wisp_bin(),
                     trace_path, dir);
    } else {
      (void)snprintf(cmd, sizeof(cmd),
                     "%s --profile-json %s %s ok >/dev/null 2>&1", wisp_bin(),
                     trace_path, dir);
    }
    int st = system(cmd);
    ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0,
           "profile JSON invocation failed for equals=%d", equals);
    ASSERT(file_contains(trace_path, "\"cat\":\"splan.store\""),
           "store trace events were not emitted for equals=%d", equals);
    ASSERT(file_contains(trace_path, "],\"displayTimeUnit\":\"ms\"}"),
           "trace was not finalized for equals=%d", equals);
  }
}

TEST(wisp_cli, profile_json_open_failure_exits_early) {
  char dir[] = "/tmp/enki-profile-missing-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  ASSERT_EQ(rmdir(dir), 0);

  char trace_path[512];
  (void)snprintf(trace_path, sizeof(trace_path), "%s/trace.json", dir);
  char cmd[2048];
  (void)snprintf(cmd, sizeof(cmd),
                 "%s --profile-json %s %s reaver >/dev/null 2>&1", wisp_bin(),
                 trace_path, reaver_plan_dir());
  int st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) != 0,
         "unopenable profile destination should fail");
  ASSERT_NEQ(access(trace_path, F_OK), 0);
}

TEST(wisp_cli, profile_json_finalizes_after_runtime_error) {
  char dir[] = "/tmp/enki-profile-error-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));

  char module_path[512];
  (void)snprintf(module_path, sizeof(module_path), "%s/bad.plan", dir);
  FILE* f = fopen(module_path, "w");
  ASSERT_NOT_NULL(f);
  fputs("((#pin \"R\") (\"Print\" \"nope\"))\n", f);
  fclose(f);

  char trace_path[512];
  (void)snprintf(trace_path, sizeof(trace_path), "%s/error.json", dir);
  char cmd[2048];
  (void)snprintf(cmd, sizeof(cmd),
                 "%s --profile-json %s %s bad >/dev/null 2>&1", wisp_bin(),
                 trace_path, dir);
  int st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) != 0,
         "runtime error should remain nonzero");
  ASSERT(file_contains(trace_path, "],\"displayTimeUnit\":\"ms\"}"),
         "runtime-error trace was not finalized");
}

/*
 * P4: actor scenarios through the boot driver — the wisp boot thread is
 * the root actor (the reference withNewRts), spawned actors run through
 * the binary's default executor, and op-82 coordination effects in the
 * run function block and resume instead of raising.
 */

static int run_scenario(const char* bin, const char* fn, char* out,
                        size_t cap) {
  char cmd[1024];
  (void)snprintf(cmd, sizeof(cmd), "%s tests/plan actors %s 2>/dev/null", bin,
                 fn);
  return run_cmd(cmd, out, cap);
}

TEST(wisp_cli, actor_ping_echo) {
  char out[256];
  int st = run_scenario(wisp_bin(), "ping", out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "ping run failed");
  ASSERT_STR_EQ(out, "hello-via-echo");
}

TEST(wisp_cli, actor_counter_holds_state) {
  char out[256];
  int st = run_scenario(wisp_bin(), "count", out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "count run failed");
  ASSERT_STR_EQ(out, "3");
}

TEST(wisp_cli, actor_deadlock_is_reported) {
  char out[256];
  int st = run_scenario(wisp_bin(), "stuck", out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) != 0,
         "an unanswerable Recv must fail the run");
}

TEST(wisp_cli, actor_recv_under_try) {
  char out[256];
  int st = run_scenario(wisp_bin(), "tryrecv", out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "tryrecv run failed");
  ASSERT_STR_EQ(out, "tm");
}

/* Differential vs the reaver oracle (a local Haskell reference build);
 * skipped where the binary is absent (e.g. the nix sandbox). */
TEST(wisp_cli, actor_differential_vs_reaver) {
  const char* oracle = getenv("ENKI_REAVER_BIN");
  if (oracle == NULL || oracle[0] == '\0')
    oracle = "./reaver/dist-newstyle/build/aarch64-osx/ghc-9.10.3/"
             "plan-assembler-0.1.0.0/x/plan-assembler/build/plan-assembler/"
             "plan-assembler";
  if (access(oracle, X_OK) != 0)
    SKIP_TEST("reaver oracle binary not available");

  static const char* const fns[] = {"ping", "count", "tryrecv"};
  for (size_t i = 0; i < sizeof(fns) / sizeof(fns[0]); i++) {
    char ours[256], theirs[256];
    int st1 = run_scenario(wisp_bin(), fns[i], ours, sizeof(ours));
    int st2 = run_scenario(oracle, fns[i], theirs, sizeof(theirs));
    ASSERT(WIFEXITED(st1) && WEXITSTATUS(st1) == 0, "wisp %s failed", fns[i]);
    ASSERT(WIFEXITED(st2) && WEXITSTATUS(st2) == 0, "reaver %s failed", fns[i]);
    ASSERT_STR_EQ(ours, theirs, "differential mismatch on %s", fns[i]);
  }
}

TEST(wisp_cli, read_file_honors_file_root) {
  char dir[] = "/tmp/enki-fileroot-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));

  char path[512];
  (void)snprintf(path, sizeof(path), "%s/snap", dir);
  ASSERT_EQ(mkdir(path, 0700), 0);
  (void)snprintf(path, sizeof(path), "%s/files", dir);
  ASSERT_EQ(mkdir(path, 0700), 0);

  (void)snprintf(path, sizeof(path), "%s/files/allowed.txt", dir);
  FILE* f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  fputs("inside-ok", f);
  fclose(f);

  (void)snprintf(path, sizeof(path), "%s/secret.txt", dir);
  f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  fputs("outside-secret", f);
  fclose(f);

  (void)snprintf(path, sizeof(path), "%s/snap/root.plan", dir);
  f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  fprintf(f, "(#bind Output\n"
             "  (#pin (#law \"Output\" (Output x) ((#pin \"R\") (\"Output\" "
             "x)))))\n"
             "(#bind ReadFile\n"
             "  (#pin (#law \"ReadFile\" (ReadFile x) ((#pin \"R\") "
             "(\"ReadFile\" x)))))\n"
             "(#bind inside\n"
             "  (#pin (#law \"inside\" (inside args) ((#pin \"R\") (\"Output\" "
             "((#pin \"R\") (\"ReadFile\" \"allowed.txt\")))))))\n"
             "(#bind escape\n"
             "  (#pin (#law \"escape\" (escape args) ((#pin \"R\") (\"Output\" "
             "((#pin \"R\") (\"ReadFile\" \"../secret.txt\")))))))\n");
  fclose(f);

  char cmd[1024];
  char out[256];

  (void)snprintf(cmd, sizeof(cmd),
                 "cd %s && %s --text-hash --file-root files snap root inside "
                 "2>/dev/null",
                 dir, wisp_bin());
  int st = run_cmd(cmd, out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "inside run failed");
  ASSERT_NOT_NULL(strstr(out, "inside-ok"), "got `%s`", out);

  (void)snprintf(cmd, sizeof(cmd),
                 "cd %s && %s --text-hash --file-root files snap root escape "
                 "2>/dev/null",
                 dir, wisp_bin());
  st = run_cmd(cmd, out, sizeof(out));
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0, "escape run failed");
  ASSERT_NULL(strstr(out, "outside-secret"), "escaped file root: `%s`", out);
}

TEST(wisp_cli, boot_reset_imports_stdlib_primitives) {
  char dir[] = "/tmp/enki-boot-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir), "failed to make temp dir");

  char src_dir[4096];
  reaver_src_dir(src_dir, sizeof(src_dir));

  char plan_dir[4096];
  int s = snprintf(plan_dir, sizeof(plan_dir), "%s/plan", src_dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(plan_dir), "reaver plan path too long");

  char cmd[16384];
  s = snprintf(cmd, sizeof(cmd),
               "cd %s && %s --file-root %s %s reaver main "
               ">reset.out 2>&1",
               dir, wisp_bin(), src_dir, plan_dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(cmd), "reset command too long");
  int st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0,
         "boot reset failed; see %s/reset.out", dir);

  s = snprintf(cmd, sizeof(cmd),
               "cd %s && %s --file-root %s snap root _ "
               ">load.out 2>&1 <<'EOF'\n"
               "(#bind std (#module std))\n"
               "(#import std)\n"
               ":*app-todo\n"
               "EOF\n",
               dir, wisp_bin(), src_dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(cmd), "load command too long");
  st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0,
         "stdlib import failed; see %s/load.out", dir);

  s = snprintf(cmd, sizeof(cmd),
               "cd %s && %s --file-root %s snap root _ "
               ">query.out 2>&1 <<'EOF'\n"
               "(Add 1 2)\n"
               "EOF\n",
               dir, wisp_bin(), src_dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(cmd), "query command too long");
  st = system(cmd);
  ASSERT(WIFEXITED(st) && WEXITSTATUS(st) == 0,
         "query failed; see %s/query.out", dir);

  char query_path[512];
  s = snprintf(query_path, sizeof(query_path), "%s/query.out", dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(query_path),
         "query output path too long");
  ASSERT_FALSE(file_contains(query_path, "(\"ERROR\""),
               "booted REPL returned an error; see %s", query_path);
  ASSERT(file_contains(query_path, "\n3\n"),
         "booted REPL did not evaluate (Add 1 2) to 3; see %s", query_path);
}
