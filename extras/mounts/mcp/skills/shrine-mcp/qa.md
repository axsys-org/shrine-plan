# QA mode

Testing is using. In QA mode you do your normal work and say what you
expect before you look. Nothing here is a test framework: it is records,
cells and the page. Someone says "QA mode on" and this page is what that
means.

## The tree

Under `/agent/<name>/qa`:

- `plan`: one child per step, `done: true` when a step is finished.
  Finishing a step is a write, so your own progress is data.
- `expect/<check>`: a record with exactly the slots you expect on the
  answer's root, written before you read the cell it is about, and the rows
  you expect beneath it when the answer has rows. Nothing else on it: the
  roots compare too.
- `check/<check>`: a `diff` cell whose input is `expect/<check>` at the
  care the answer has, and whose `other` is the cell's `/x` at the same
  care; that `other` is the record of which cell the check is about.
  `changed: 0, added: 0, removed: 0` means you were right.
- `zeros/<check>`: `{added: 0, removed: 0, changed: 0}`, written with the
  expectation.
- `board`: a `gather` over `zeros` whose secondary inputs are every check's
  `/x`, one slot per check name. `score`: a `diff` of `board` against
  `zeros`. One number, `/changed`: how many checks disagree now.
- `bugs/<name>`: when the world is wrong. The smallest repro as a record:
  the calls, the path, what came back, what should have.
- `notes/<name>`: when you were wrong. What you expected, why it was
  reasonable, what the page or the doc should have said.

## The rules

1. Write the expectation first, read second. An expectation written after
   the read is a description, not a test.
2. When a check disagrees, decide which side is wrong before anything else,
   and record it under `bugs` or `notes`. Both are findings.
3. Do not fix the world mid-run. Record it, keep going.
4. Read both sides of a diff at the same care.
5. Keep the live page open on `/agent/<name>/qa` as well as where you work.
   Anything it shows that is not what you wrote is a row under `notes`.
6. Mirror `bugs` and `score` to a file at the end of each stretch, until a
   world is proven to keep its records across a reboot.

QA happens behind the work. The person's page stays on their folder; the
score sits in its header as a chip, green at zero, the count otherwise, and
a click opens the QA view. Open that view for the person only when they
ask, or when the score is not zero and the disagreement is about something
they are looking at.

The report is the score and the bug folder, not the story. Someone opening
`/live?views=/agent/<name>/qa` should see the plan, the score and the bugs
without reading anything else. Bug lists from different testers compose
with `gather` like everything else.
