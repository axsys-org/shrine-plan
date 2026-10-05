#ifndef PLAN_BYTECODE_H
#define PLAN_BYTECODE_H
#include "plan/value.h"

typedef uint64_t pl_op_t; /* one slot per opcode and per operand */

typedef struct pl_code {
  pl_op_t* ops;
  size_t nops;
  uint64_t strict_mask;  /* nonzero: the law pre-forces these args (bit
                            i-1 = arg i) in its checked prologue */
  uint32_t strict_entry; /* fast entry: skips the checked prologue; judge
                            takes it iff every strict arg already is a
                            value (pl_strict_entry), never on a hint */
  uint32_t max_var;      /* highest OP_PUSH_VAR operand (UINT32_MAX when the
                            program contains OP_INTERP, whose expr operands
                            reference env vars invisibly).  max_var <= arity
                            means the code never reads chain-bind slots, so
                            judge can skip the chain scan and enter with the
                            [head, args…] group left on the value stack. */
} pl_code;

typedef enum pl_op {
  OP_PUSH_VAR = 0,    /* +slot: push env slot                              */
  OP_PUSH_LIT = 1,    /* +val: push literal                                */
  OP_MK_THK = 2,      /* +argc +bane[|NOUPD] (+op +name when KNOWN)        */
  OP_FORCE = 3,       /* pop, evaluate to WHNF, push the result            */
  OP_CALL = 4,        /* +target +argc: local block call; args become the  */
                      /* callee's operand-stack base; result arrives WHNF  */
  OP_TAILCALL = 5,    /* ingest-fused MK_THK+RET                           */
  OP_INTERP = 6,      /* +expr: interpret a kal expr under the env         */
  OP_RET = 7,         /* pop, reset the operand stack, return              */
  OP_MK_APP = 8,      /* +argc: build an app (WHNF) from head + args       */
  OP_PUSH_SLOT = 9,   /* +n: re-push operand-stack slot argbase+n          */
  OP_BR = 10,         /* +m +t0..t(m-1): pop nat scrutinee, jump to arm    */
  OP_JMP = 11,        /* +target: unconditional jump                       */
  OP_ENTRY = 12,      /* +mask: fast-entry marker after the strict-arg     */
                      /* prologue; a no-op when fallen through             */
                      /* Direct calls: eager call sites that would build a
                       * thunk cell and FORCE it on the next instruction
                       * instead enter the callee straight from the stack
                       * operands; the result arrives via ret_exec at the
                       * same slot the cell would have occupied. */
  OP_CALL_KNOWN = 13, /* +argc +op +name: resolved primop, args on stack */
  OP_CALL_FAST = 14,  /* +argc +hint: [head, args…] on stack; verified
                       * exact-arity law entry; the hint operand is the
                       * caller's strict mask, informational only (the
                       * entry is decided by checking the arguments);
                       * anything else degrades to slow apply           */
  OP_CALL_SLOW = 15,  /* +argc: [head, args…] on stack; generic apply   */
  /* Ingest-only numeric specialisations. Operands match CALL_KNOWN for
   * ordinary calls and MK_THK for tail calls. Never accepted in a row. */
  OP_ADD = 16,
  OP_SUB = 17,
  OP_CMP = 18,
  OP_TAIL_ADD = 19,
  OP_TAIL_SUB = 20,
  OP_TAIL_CMP = 21,
  /* Ingest-proven WHNF entries; operand widths are unchanged. */
  OP_FORCE_READY = 22,
  OP_RET_READY = 23,
  OP_CALL_READY = 24,
  OP_TAIL_READY = 25,
  /* Ingest-only filler: a MK_THK KNOWN (4 operands) rewritten into a
   * CALL_KNOWN (3 operands) leaves one slot behind. */
  OP_NOP = 26,
  PL_OP_COUNT = 27 /* sentinel: sizes pl_run's exec dispatch table */
} pl_op;

pl_code* pl_bytecode_from_val(pl_val val);
void pl_bytecode_free(pl_code* code);

#endif
