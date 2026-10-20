# Kernel asks

Two things the mcp mount does today that belong in the kernel.

1. **The dependency index, readable.** The kernel keeps, for invalidation, which cells read which paths. The mount cannot read it, so `referenced_by` on the thing view (`read path=<thing> thing=true`) walks the last 400 events of the journal for records and tacks pointing at the thing. With the index readable (a peek that answers, for a path, the cells and records referencing it), `referenced_by` is one lookup, complete, and not windowed.
2. **`if_case` as a kernel precondition.** The mount's write-only-if-unchanged reads the record's case and then writes, two supervisor turns; a case precondition on the writ itself would refuse inside the commit, one turn, with the refusal naming the case as today.
