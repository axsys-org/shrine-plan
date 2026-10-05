# Grove, start to finish: the frame-by-frame account

Companion to `grove-start-to-finish.mp4`: **5:51**, 1280×720, 25 fps, 8776 frames. The playable source is `demo.html`; Space pauses and `r` restarts.

This document is **generated from the same timeline that renders the video**. Every action in the script records a beat at the instant it starts, so the times and frame numbers below are exact, not estimated.

**This is one continuous story.** It uses the same data, the same component names, the same scores and the same rules as `spec/BEHAVIOR-SPEC.md` and `spec/prototype/` (the scores were computed by the prototype's `enumerate()`). It replaces the five earlier demo videos, which disagreed with each other on names, numbers and order. Where anything here disagrees with the spec, **the spec wins**.

## How to read this

### Timestamps and frames
Each row has a time (`m:ss.ss` from the start of the video) and the frame it starts on (`frame = ⌊t × 25⌋`). A row lasts until the next row starts. Between rows, the screen only:
- moves the cursor along an ease-in-out path;
- fades an element in or out (≈0.3–0.4 s);
- re-renders live values that depend on data (counts, progress, the dial).

### Kinds of row
| Mark | Meaning |
|---|---|
| 🖱 move | the cursor travels to a target (eased; no click yet) |
| 🖱 click | press and release; a ring ripples out from the cursor tip for 0.28 s |
| 🖱 press + drag | mouse down on a source, then motion while held; a ghost chip follows the cursor when dragging data |
| 🖱 release | mouse up over the drop target |
| ⌨ type | characters appear one by one with a ▍ caret; the count of keystrokes is given |
| ⌨ key | a key or shortcut, shown as a keycap overlay for 1 s |
| 👁 screen | what visibly changed (written for a reader who can’t see the frame) |
| ⚙ local | an action logged by the engine with **no model** (teal stripe in the log) |
| ✎ data write | a write to a record (orange stripe in the log); always one undoable step |
| ◆ jev | a fast decision: a pick among engine-built candidates, with latency and tokens |
| ◆◆ large model | new logic authored as one pure function, then checked |
| ▤ decision panel / contract card / inspector | the right-hand panel’s content at that moment |
| ↳ underneath | what the engine computed, with no visual of its own |

The **L / J / G** column gives the running counters shown at the top of the log panel (local · jev · large model) *after* that row.

## The screen, fixed for the whole video (pixels at 1280×720)

| Region | Box (x, y, w, h) | Contents |
|---|---|---|
| Top bar | 0, 0, 1280, 44 | “Grove” · tabs **Renovation job** / **Component maker** / + · Undo · ↻ reload · AI switch (green dot “jev + large model”, grey “AI off”) |
| Palette | 0, 44, 220, 676 | **Atoms** (rect, ellipse, line, text, frame, input, button) · **Components** (Board, Table, List, Form, Dial, Map not installed; yours appear in purple) · **Namespace · data** (one card per collection with field chips `name role`; 🔒 = read-only) + “+ New collection” and “⇢ Connect” · **Namespace · screen** (one pill per placed element) |
| Ask bar | 220, 44, 790, 44 | purple-bordered prompt; in the maker it becomes “Making: name · version · Save to palette” |
| Canvas | 220, 88, 790, 540 visible | dotted grid; two areas side by side, 800 px apart; the view pans between them. Overlays (collection editor, record form) sit above the canvas and do not pan |
| Right panel | 1010, 44, 270, 356 | changes with context: **Decision** (candidates with score bars, the winner outlined, latency and tokens, the reason), **Contract** (in the maker), **Inspector** (static / source / input per property), **Schema** (after creating a collection) |
| Log | 1010, 400, 270, ~228 | three counters, then the newest 9 actions, newest first, with a coloured stripe: teal local · orange write · purple jev · magenta large model |
| Caption | 0, 628, 1280, 92 | chapter number, title and one-line explanation; a small clock above its right corner |

**Colour language, used the same everywhere:**
- **teal:** data / from a source;
- **orange:** input / writes;
- **purple:** jev and user-made components;
- **magenta:** the large model;
- **dashed amber:** a hole;
- **green outline:** something new.

Timeline bar colours:
- To do: blue-grey;
- Doing: amber;
- Done: green;
- critical path: orange-red;
- Bookings: teal.

## 0 · Title card (0:00.00 – 0:10.64)

A full-screen dark card, “GROVE · START TO FINISH”, with the heading **“From an empty namespace to a working app you built yourself.”** Below it are eight tiles naming the parts: Collections, Records, Drag + ask, Static · source · input, Holes, Component maker, Reuse, and Versions, reload, AI off. It holds for 9.8 s, then fades over 0.84 s, revealing the empty workspace.

## 1 · An empty workspace  (0:10.64 – 0:24.43 · frames 266–609)

> **Caption:** Nothing exists yet. Left: atoms, components, and one namespace for data and screen elements. Top: Ask. Right: decisions and a log of who handled each action.

### Underneath

No state exists. `namespace = {}`; `screen = []`; `registry = {Board, Table, List, Form, Dial (installed), Map (known, not installed)}`. Counters start at 0. The cursor tour only adds a highlight ring (`.hlx`) around each region in turn. It changes no state.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 0:13.30 | 332 | 👁 screen | The canvas is empty except for a dashed hint. The data namespace is empty; Components shows the prepared set (Board, Table, List, Form, Dial) and Map greyed out as not installed. Counters read local 0 · jev 0 · large model 0. | 0 / 0 / 0 |
| 0:13.30 | 332 | 🖱 move | cursor → the Atoms section | 0 / 0 / 0 |
| 0:15.47 | 386 | 🖱 move | cursor → the Components section | 0 / 0 / 0 |
| 0:17.64 | 441 | 🖱 move | cursor → the Namespace · data section | 0 / 0 / 0 |
| 0:19.81 | 495 | 🖱 move | cursor → the Namespace · screen section | 0 / 0 / 0 |
| 0:21.98 | 549 | 🖱 move | cursor → the log and counters | 0 / 0 / 0 |

**State at the end of chapter 1:** counters local 0 · jev 0 · large 0.

## 2 · Create a collection: People  (0:24.43 – 0:34.86 · frames 610–870)

> **Caption:** Click “+ New collection”, name it, add a field and pick its type. The role (title, group, start…) is inferred locally from the name and type. No model.

### Underneath

- Clicking “+ New collection” opens the **collection editor**, an overlay that is not part of the canvas. Its fixed parts:
  - a Name box;
  - field rows of name, type, role and writes;
  - “+ field”;
  - “Create collection”.
- Typing the name “People” names the namespace variable. The record type is named in the singular (**Person**) automatically.
- Choosing **Text** for `name` runs `inferRole(field, allFields)` locally. A Text field named `name` is in the title list, so it gets **role title**. A role is a hint for matching, never a constraint, and the user can override it.
- Every field is **writable** by default (the orange toggle). Only a source can make a field read-only (see chapter 14).
- “Create collection” commits `People : Many<Person{name: Text}>` and logs one local action. The right panel shows the type as a live schema card.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 0:27.09 | 677 | 🖱 click | cursor travels to “+ New collection” in the palette (0.70 s), then clicks | 0 / 0 / 0 |
| 0:28.07 | 701 | 🖱 click | cursor travels to the collection Name box (0.70 s), then clicks | 0 / 0 / 0 |
| 0:29.05 | 726 | ⌨ type | types “People” into the Name box (6 keys) | 0 / 0 / 0 |
| 0:29.52 | 737 | ↳ underneath | the name becomes the collection’s namespace variable; the record type is named Person (singular) automatically | 0 / 0 / 0 |
| 0:29.52 | 737 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 0 / 0 / 0 |
| 0:30.36 | 758 | 🖱 click | cursor travels to the field-name box on row 1 (0.49 s), then clicks | 0 / 0 / 0 |
| 0:31.13 | 778 | ⌨ type | types “name” into field name 1 (4 keys) | 0 / 0 / 0 |
| 0:31.41 | 785 | 🖱 click | cursor travels to the type box on row 1 (0.49 s), then clicks | 0 / 0 / 0 |
| 0:32.53 | 813 | 🖱 click | cursor travels to “Text” in the menu (0.42 s), then clicks | 0 / 0 / 0 |
| 0:33.40 | 834 | 👁 screen | row 1 now reads: name : Text · role title · writable | 0 / 0 / 0 |
| 0:33.40 | 834 | ⚙ local | name: Text → role title (inferRole) | 1 / 0 / 0 |
| 0:33.40 | 834 | 🖱 click | cursor travels to “Create collection” (0.63 s), then clicks | 1 / 0 / 0 |
| 0:34.30 | 857 | 👁 screen | the editor closes; “People” appears under Namespace · data with its field chips | 1 / 0 / 0 |
| 0:34.30 | 857 | ⚙ local | + People : Many<Person> · 1 fields | 2 / 0 / 0 |

**State at the end of chapter 2:** counters local 2 · jev 0 · large 0.

## 3 · Add records with a form built from the type  (0:34.86 – 0:43.21 · frames 871–1079)

> **Caption:** A Text field gives a text input. Type a name, Add, repeat. Each Add writes one Person; the table underneath shows what exists.

### Underneath

- The form is built **from the type**. There is no model and no layout guess. Each field type has exactly one default control:
  - Text → text input;
  - Enum → segmented choice;
  - Ref → picker over the target collection;
  - Date → calendar;
  - Duration → stepper;
  - Many → multi-picker.
- “Add record” is one transaction. It creates one record, appends it to the table under the form, bumps the count on the palette card, then clears the form.
- Each Add is logged as a **data write** (local). The ids are `p1`, `p2` and `p3`, in order.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 0:37.52 | 938 | 👁 screen | a form appears on the right with one text input labelled “name”, an Add record button, and an empty record table | 2 / 0 / 0 |
| 0:37.52 | 938 | 🖱 click | cursor travels to the “name” control (0.42 s), then clicks | 2 / 0 / 0 |
| 0:38.23 | 955 | ⌨ type | types “Ana” into the name input (3 keys) | 2 / 0 / 0 |
| 0:38.42 | 960 | 🖱 click | cursor travels to “Add record” (0.49 s), then clicks | 2 / 0 / 0 |
| 0:39.19 | 979 | ✎ data write | create People#p1 { name: “Ana” } | 3 / 0 / 0 |
| 0:39.19 | 979 | 🖱 click | cursor travels to the “name” control (0.42 s), then clicks | 3 / 0 / 0 |
| 0:39.89 | 997 | ⌨ type | types “Sam” into the name input (3 keys) | 3 / 0 / 0 |
| 0:40.08 | 1001 | 🖱 click | cursor travels to “Add record” (0.49 s), then clicks | 3 / 0 / 0 |
| 0:40.85 | 1021 | ✎ data write | create People#p2 { name: “Sam” } | 4 / 0 / 0 |
| 0:40.85 | 1021 | 🖱 click | cursor travels to the “name” control (0.42 s), then clicks | 4 / 0 / 0 |
| 0:41.55 | 1038 | ⌨ type | types “Lee” into the name input (3 keys) | 4 / 0 / 0 |
| 0:41.74 | 1043 | 🖱 click | cursor travels to “Add record” (0.49 s), then clicks | 4 / 0 / 0 |
| 0:42.51 | 1062 | ✎ data write | create People#p3 { name: “Lee” } | 5 / 0 / 0 |

**State at the end of chapter 3:** counters local 5 · jev 0 · large 0.

## 4 · Create Tasks: six fields, six types  (0:43.21 – 1:21.38 · frames 1080–2033)

> **Caption:** title Text · status Enum (To do, Doing, Done) · assignee → People · start Date · duration Duration · depends_on Many → Tasks. Watch the roles fill in as each type is chosen.

### Underneath

Choosing each type runs `inferRole` on that row immediately:
- `title: Text` → title.
- `status: Enum` → **group**, because an Enum named status/stage/state/phase/category/type is a grouping.
  - Values are typed one at a time; Enter makes each one a chip.
  - “ordered” is ticked, so column order is the value order.
- `assignee: Ref → People` → **ref**. The Ref picker lists existing collections; People has 3 records.
- `start: Date` → **start**.
- `duration: Duration` → **duration**.
- `depends_on: Many → Tasks` → **no role**. The picker offers “Tasks (this collection)” because a collection may refer to itself.

The result is `Tasks : Many<Task{title, status, assignee, start, duration, depends_on}>` with 5 role-bearing fields. Role-bearing fields are what “coverage” counts later.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 0:45.87 | 1146 | 🖱 click | cursor travels to “+ New collection” in the palette (0.70 s), then clicks | 5 / 0 / 0 |
| 0:46.85 | 1171 | 🖱 click | cursor travels to the collection Name box (0.70 s), then clicks | 5 / 0 / 0 |
| 0:47.83 | 1195 | ⌨ type | types “Tasks” into the Name box (5 keys) | 5 / 0 / 0 |
| 0:48.22 | 1205 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 5 / 0 / 0 |
| 0:49.06 | 1226 | 🖱 click | cursor travels to the field-name box on row 1 (0.49 s), then clicks | 5 / 0 / 0 |
| 0:49.83 | 1245 | ⌨ type | types “title” into field name 1 (5 keys) | 5 / 0 / 0 |
| 0:50.18 | 1254 | 🖱 click | cursor travels to the type box on row 1 (0.49 s), then clicks | 5 / 0 / 0 |
| 0:51.30 | 1282 | 🖱 click | cursor travels to “Text” in the menu (0.42 s), then clicks | 5 / 0 / 0 |
| 0:52.16 | 1304 | 👁 screen | row 1 now reads: title : Text · role title · writable | 5 / 0 / 0 |
| 0:52.16 | 1304 | ⚙ local | title: Text → role title (inferRole) | 6 / 0 / 0 |
| 0:52.16 | 1304 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 6 / 0 / 0 |
| 0:53.00 | 1325 | 🖱 click | cursor travels to the field-name box on row 2 (0.49 s), then clicks | 6 / 0 / 0 |
| 0:53.77 | 1344 | ⌨ type | types “status” into field name 2 (6 keys) | 6 / 0 / 0 |
| 0:54.19 | 1354 | 🖱 click | cursor travels to the type box on row 2 (0.49 s), then clicks | 6 / 0 / 0 |
| 0:55.31 | 1382 | 🖱 click | cursor travels to “Enum…” in the menu (0.42 s), then clicks | 6 / 0 / 0 |
| 0:56.18 | 1404 | ⌨ type | types “To do” into the enum values box (5 keys) | 6 / 0 / 0 |
| 0:56.57 | 1414 | ⌨ key | presses Enter · value “To do” becomes a chip | 6 / 0 / 0 |
| 0:57.55 | 1438 | ⌨ type | types “Doing” into the enum values box (5 keys) | 6 / 0 / 0 |
| 0:57.94 | 1448 | ⌨ key | presses Enter · value “Doing” becomes a chip | 6 / 0 / 0 |
| 0:58.92 | 1473 | ⌨ type | types “Done” into the enum values box (4 keys) | 6 / 0 / 0 |
| 0:59.23 | 1480 | ⌨ key | presses Enter · value “Done” becomes a chip | 6 / 0 / 0 |
| 1:00.63 | 1515 | 👁 screen | row 2 now reads: status : Enum · To do, Doing, Done · role group · writable | 6 / 0 / 0 |
| 1:00.63 | 1515 | ⚙ local | status: Enum · To do, Doing, Done → role group (inferRole) | 7 / 0 / 0 |
| 1:00.63 | 1515 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 7 / 0 / 0 |
| 1:01.47 | 1536 | 🖱 click | cursor travels to the field-name box on row 3 (0.49 s), then clicks | 7 / 0 / 0 |
| 1:02.24 | 1556 | ⌨ type | types “assignee” into field name 3 (8 keys) | 7 / 0 / 0 |
| 1:02.80 | 1570 | 🖱 click | cursor travels to the type box on row 3 (0.49 s), then clicks | 7 / 0 / 0 |
| 1:03.92 | 1598 | 🖱 click | cursor travels to “Ref →” in the menu (0.42 s), then clicks | 7 / 0 / 0 |
| 1:05.14 | 1628 | 🖱 click | cursor travels to “People” in the menu (0.42 s), then clicks | 7 / 0 / 0 |
| 1:06.01 | 1650 | 👁 screen | row 3 now reads: assignee : → People · role ref · writable | 7 / 0 / 0 |
| 1:06.01 | 1650 | ⚙ local | assignee: → People → role ref (inferRole) | 8 / 0 / 0 |
| 1:06.01 | 1650 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 8 / 0 / 0 |
| 1:06.85 | 1671 | 🖱 click | cursor travels to the field-name box on row 4 (0.49 s), then clicks | 8 / 0 / 0 |
| 1:07.62 | 1690 | ⌨ type | types “start” into field name 4 (5 keys) | 8 / 0 / 0 |
| 1:07.97 | 1699 | 🖱 click | cursor travels to the type box on row 4 (0.49 s), then clicks | 8 / 0 / 0 |
| 1:09.09 | 1727 | 🖱 click | cursor travels to “Date” in the menu (0.42 s), then clicks | 8 / 0 / 0 |
| 1:09.95 | 1748 | 👁 screen | row 4 now reads: start : Date · role start · writable | 8 / 0 / 0 |
| 1:09.95 | 1748 | ⚙ local | start: Date → role start (inferRole) | 9 / 0 / 0 |
| 1:09.95 | 1748 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 9 / 0 / 0 |
| 1:10.80 | 1769 | 🖱 click | cursor travels to the field-name box on row 5 (0.49 s), then clicks | 9 / 0 / 0 |
| 1:11.56 | 1789 | ⌨ type | types “duration” into field name 5 (8 keys) | 9 / 0 / 0 |
| 1:12.12 | 1803 | 🖱 click | cursor travels to the type box on row 5 (0.49 s), then clicks | 9 / 0 / 0 |
| 1:13.25 | 1831 | 🖱 click | cursor travels to “Duration” in the menu (0.42 s), then clicks | 9 / 0 / 0 |
| 1:14.11 | 1852 | 👁 screen | row 5 now reads: duration : Duration (days) · role duration · writable | 9 / 0 / 0 |
| 1:14.11 | 1852 | ⚙ local | duration: Duration (days) → role duration (inferRole) | 10 / 0 / 0 |
| 1:14.11 | 1852 | 🖱 click | cursor travels to “+ field” (0.56 s), then clicks | 10 / 0 / 0 |
| 1:14.95 | 1873 | 🖱 click | cursor travels to the field-name box on row 6 (0.49 s), then clicks | 10 / 0 / 0 |
| 1:15.72 | 1893 | ⌨ type | types “depends_on” into field name 6 (10 keys) | 10 / 0 / 0 |
| 1:16.42 | 1910 | 🖱 click | cursor travels to the type box on row 6 (0.49 s), then clicks | 10 / 0 / 0 |
| 1:17.54 | 1938 | 🖱 click | cursor travels to “Many →” in the menu (0.42 s), then clicks | 10 / 0 / 0 |
| 1:18.76 | 1969 | 🖱 click | cursor travels to “Tasks” in the menu (0.42 s), then clicks | 10 / 0 / 0 |
| 1:19.63 | 1990 | 👁 screen | row 6 now reads: depends_on : Many → Tasks · writable | 10 / 0 / 0 |
| 1:19.63 | 1990 | ⚙ local | depends_on: Many → Tasks → role none (inferRole) | 11 / 0 / 0 |
| 1:19.63 | 1990 | ↳ underneath | depends_on has no role: nothing in the role table matches “depends_on”. It is still a normal field; components can read it, and later the large model’s function does | 11 / 0 / 0 |
| 1:19.63 | 1990 | 🖱 click | cursor travels to “Create collection” (0.63 s), then clicks | 11 / 0 / 0 |
| 1:20.54 | 2013 | 👁 screen | the editor closes; “Tasks” appears under Namespace · data with its field chips | 11 / 0 / 0 |
| 1:20.54 | 2013 | ⚙ local | + Tasks : Many<Task> · 6 fields | 12 / 0 / 0 |

**State at the end of chapter 4:** counters local 12 · jev 0 · large 0.

## 5 · Add tasks: every control comes from a type  (1:21.38 – 1:53.62 · frames 2034–2839)

> **Caption:** Text → input. Enum → segmented choice. Ref → picker over People. Date → calendar. Duration → stepper. Many → multi-picker over Tasks. Two by hand, then six more, faster.

### Underneath

- The form is built from the type (see chapter 3).
- The **assignee** picker reads People live, so it shows Ana, Sam and Lee.
- The **depends on** picker reads Tasks live, so it only offers tasks that already exist.
- The **duration** stepper starts at 1 d; each “+” adds a day.
- The ×4 badge means the same interactions at four times speed. Nothing different happens underneath.
- After this chapter, the data is exactly the prototype seed (`t1`–`t8`):
  - Demo walls · Done · Ana · Oct 1 · 2 d
  - Order fixtures · Done · Lee · Oct 1 · 2 d
  - Electrical · Doing · Sam · Oct 3 · 3 d · after Demo walls
  - Plumbing · Doing · Lee · Oct 3 · 3 d · after Demo walls
  - Drywall · To do · Ana · Oct 6 · 3 d · after Electrical, Plumbing
  - Paint · To do · Sam · Oct 9 · 2 d · after Drywall
  - Floors · To do · Lee · Oct 11 · 3 d · after Paint
  - Final clean · To do · Ana · Oct 14 · 1 d · after Floors

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 1:24.04 | 2100 | 🖱 click | cursor travels to the “title” control (0.42 s), then clicks | 12 / 0 / 0 |
| 1:24.74 | 2118 | ⌨ type | types “Demo walls” into the title input (10 keys) | 12 / 0 / 0 |
| 1:25.38 | 2134 | 🖱 click | cursor travels to “Done” on the status control (0.42 s), then clicks | 12 / 0 / 0 |
| 1:26.08 | 2151 | 🖱 click | cursor travels to the “assignee” control (0.42 s), then clicks | 12 / 0 / 0 |
| 1:27.06 | 2176 | 🖱 click | cursor travels to “Ana” in the menu (0.42 s), then clicks | 12 / 0 / 0 |
| 1:27.92 | 2198 | 🖱 click | cursor travels to the “start” control (0.42 s), then clicks | 12 / 0 / 0 |
| 1:28.90 | 2222 | 🖱 click | cursor travels to Oct 1 in the date picker (0.42 s), then clicks | 12 / 0 / 0 |
| 1:29.74 | 2243 | 🖱 click | cursor travels to the “+” on duration (0.42 s), then clicks | 12 / 0 / 0 |
| 1:30.44 | 2261 | 🖱 click | cursor travels to “Add record” (0.49 s), then clicks | 12 / 0 / 0 |
| 1:31.21 | 2280 | ✎ data write | create Tasks#t1 { title: “Demo walls”, status: Done, assignee: Ana, start: Oct 1, duration: 2 d } | 13 / 0 / 0 |
| 1:31.21 | 2280 | 🖱 click | cursor travels to the “title” control (0.42 s), then clicks | 13 / 0 / 0 |
| 1:31.91 | 2297 | ⌨ type | types “Order fixtures” into the title input (14 keys) | 13 / 0 / 0 |
| 1:32.80 | 2320 | 🖱 click | cursor travels to “Done” on the status control (0.42 s), then clicks | 13 / 0 / 0 |
| 1:33.50 | 2337 | 🖱 click | cursor travels to the “assignee” control (0.42 s), then clicks | 13 / 0 / 0 |
| 1:34.48 | 2362 | 🖱 click | cursor travels to “Lee” in the menu (0.42 s), then clicks | 13 / 0 / 0 |
| 1:35.35 | 2383 | 🖱 click | cursor travels to the “start” control (0.42 s), then clicks | 13 / 0 / 0 |
| 1:36.33 | 2408 | 🖱 click | cursor travels to Oct 1 in the date picker (0.42 s), then clicks | 13 / 0 / 0 |
| 1:37.17 | 2429 | 🖱 click | cursor travels to the “+” on duration (0.42 s), then clicks | 13 / 0 / 0 |
| 1:37.87 | 2446 | 🖱 click | cursor travels to “Add record” (0.49 s), then clicks | 13 / 0 / 0 |
| 1:38.64 | 2466 | ✎ data write | create Tasks#t2 { title: “Order fixtures”, status: Done, assignee: Lee, start: Oct 1, duration: 2 d } | 14 / 0 / 0 |
| 1:38.64 | 2466 | 👁 screen | a “×4 · same form, faster” badge appears: the next six records are entered the same way at four times the speed | 14 / 0 / 0 |
| 1:38.64 | 2466 | 🖱 click | cursor travels to the “title” control (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:38.82 | 2470 | ⌨ type | types “Electrical” into the title input (10 keys) *(×4)* | 14 / 0 / 0 |
| 1:38.98 | 2474 | 🖱 click | cursor travels to “Doing” on the status control (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:39.15 | 2478 | 🖱 click | cursor travels to the “assignee” control (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:39.40 | 2484 | 🖱 click | cursor travels to “Sam” in the menu (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:39.61 | 2490 | 🖱 click | cursor travels to the “start” control (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:39.86 | 2496 | 🖱 click | cursor travels to Oct 3 in the date picker (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:40.07 | 2501 | 🖱 click | cursor travels to the “+” on duration (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:40.29 | 2507 | 🖱 click | click · “+” (now 3 d) *(×4)* | 14 / 0 / 0 |
| 1:40.36 | 2508 | 🖱 click | cursor travels to the “depends on” control (0.10 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:40.60 | 2515 | 🖱 click | cursor travels to “Demo walls” in the menu (0.09 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:40.81 | 2520 | 🖱 click | cursor travels to “Add record” (0.12 s), then clicks *(×4)* | 14 / 0 / 0 |
| 1:41.00 | 2525 | ✎ data write | create Tasks#t3 { title: “Electrical”, status: Doing, assignee: Sam, start: Oct 3, duration: 3 d, depends_on: [Demo walls] } *(×4)* | 15 / 0 / 0 |
| 1:41.00 | 2525 | 🖱 click | cursor travels to the “title” control (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:41.18 | 2529 | ⌨ type | types “Plumbing” into the title input (8 keys) *(×4)* | 15 / 0 / 0 |
| 1:41.31 | 2532 | 🖱 click | cursor travels to “Doing” on the status control (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:41.48 | 2537 | 🖱 click | cursor travels to the “assignee” control (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:41.72 | 2543 | 🖱 click | cursor travels to “Lee” in the menu (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:41.94 | 2548 | 🖱 click | cursor travels to the “start” control (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:42.19 | 2554 | 🖱 click | cursor travels to Oct 3 in the date picker (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:42.40 | 2559 | 🖱 click | cursor travels to the “+” on duration (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:42.61 | 2565 | 🖱 click | click · “+” (now 3 d) *(×4)* | 15 / 0 / 0 |
| 1:42.68 | 2567 | 🖱 click | cursor travels to the “depends on” control (0.10 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:42.93 | 2573 | 🖱 click | cursor travels to “Demo walls” in the menu (0.09 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:43.14 | 2578 | 🖱 click | cursor travels to “Add record” (0.12 s), then clicks *(×4)* | 15 / 0 / 0 |
| 1:43.33 | 2583 | ✎ data write | create Tasks#t4 { title: “Plumbing”, status: Doing, assignee: Lee, start: Oct 3, duration: 3 d, depends_on: [Demo walls] } *(×4)* | 16 / 0 / 0 |
| 1:43.33 | 2583 | 🖱 click | cursor travels to the “title” control (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:43.51 | 2587 | ⌨ type | types “Drywall” into the title input (7 keys) *(×4)* | 16 / 0 / 0 |
| 1:43.62 | 2590 | 🖱 click | cursor travels to “To do” on the status control (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:43.79 | 2594 | 🖱 click | cursor travels to the “assignee” control (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:44.04 | 2600 | 🖱 click | cursor travels to “Ana” in the menu (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:44.25 | 2606 | 🖱 click | cursor travels to the “start” control (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:44.50 | 2612 | 🖱 click | cursor travels to Oct 6 in the date picker (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:44.71 | 2617 | 🖱 click | cursor travels to the “+” on duration (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:44.93 | 2623 | 🖱 click | click · “+” (now 3 d) *(×4)* | 16 / 0 / 0 |
| 1:45.00 | 2624 | 🖱 click | cursor travels to the “depends on” control (0.10 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:45.24 | 2631 | 🖱 click | cursor travels to “Electrical” in the menu (0.09 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:45.40 | 2635 | 🖱 click | cursor travels to “Plumbing” in the menu (0.09 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:45.61 | 2640 | 🖱 click | cursor travels to “Add record” (0.12 s), then clicks *(×4)* | 16 / 0 / 0 |
| 1:45.80 | 2645 | ✎ data write | create Tasks#t5 { title: “Drywall”, status: To do, assignee: Ana, start: Oct 6, duration: 3 d, depends_on: [Electrical, Plumbing] } *(×4)* | 17 / 0 / 0 |
| 1:45.80 | 2645 | 🖱 click | cursor travels to the “title” control (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:45.98 | 2649 | ⌨ type | types “Paint” into the title input (5 keys) *(×4)* | 17 / 0 / 0 |
| 1:46.06 | 2651 | 🖱 click | cursor travels to “To do” on the status control (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:46.23 | 2655 | 🖱 click | cursor travels to the “assignee” control (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:46.48 | 2661 | 🖱 click | cursor travels to “Sam” in the menu (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:46.69 | 2667 | 🖱 click | cursor travels to the “start” control (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:46.94 | 2673 | 🖱 click | cursor travels to Oct 9 in the date picker (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:47.15 | 2678 | 🖱 click | cursor travels to the “+” on duration (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:47.32 | 2683 | 🖱 click | cursor travels to the “depends on” control (0.10 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:47.57 | 2689 | 🖱 click | cursor travels to “Drywall” in the menu (0.09 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:47.78 | 2694 | 🖱 click | cursor travels to “Add record” (0.12 s), then clicks *(×4)* | 17 / 0 / 0 |
| 1:47.97 | 2699 | ✎ data write | create Tasks#t6 { title: “Paint”, status: To do, assignee: Sam, start: Oct 9, duration: 2 d, depends_on: [Drywall] } *(×4)* | 18 / 0 / 0 |
| 1:47.97 | 2699 | 🖱 click | cursor travels to the “title” control (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:48.15 | 2703 | ⌨ type | types “Floors” into the title input (6 keys) *(×4)* | 18 / 0 / 0 |
| 1:48.24 | 2706 | 🖱 click | cursor travels to “To do” on the status control (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:48.42 | 2710 | 🖱 click | cursor travels to the “assignee” control (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:48.66 | 2716 | 🖱 click | cursor travels to “Lee” in the menu (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:48.88 | 2721 | 🖱 click | cursor travels to the “start” control (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:49.12 | 2728 | 🖱 click | cursor travels to Oct 11 in the date picker (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:49.33 | 2733 | 🖱 click | cursor travels to the “+” on duration (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:49.55 | 2738 | 🖱 click | click · “+” (now 3 d) *(×4)* | 18 / 0 / 0 |
| 1:49.62 | 2740 | 🖱 click | cursor travels to the “depends on” control (0.10 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:49.87 | 2746 | 🖱 click | cursor travels to “Paint” in the menu (0.09 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:50.08 | 2751 | 🖱 click | cursor travels to “Add record” (0.12 s), then clicks *(×4)* | 18 / 0 / 0 |
| 1:50.27 | 2756 | ✎ data write | create Tasks#t7 { title: “Floors”, status: To do, assignee: Lee, start: Oct 11, duration: 3 d, depends_on: [Paint] } *(×4)* | 19 / 0 / 0 |
| 1:50.27 | 2756 | 🖱 click | cursor travels to the “title” control (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:50.44 | 2761 | ⌨ type | types “Final clean” into the title input (11 keys) *(×4)* | 19 / 0 / 0 |
| 1:50.62 | 2765 | 🖱 click | cursor travels to “To do” on the status control (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:50.79 | 2769 | 🖱 click | cursor travels to the “assignee” control (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:51.04 | 2775 | 🖱 click | cursor travels to “Ana” in the menu (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:51.25 | 2781 | 🖱 click | cursor travels to the “start” control (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:51.50 | 2787 | 🖱 click | cursor travels to Oct 14 in the date picker (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:51.71 | 2792 | 🖱 click | cursor travels to the “depends on” control (0.10 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:51.95 | 2798 | 🖱 click | cursor travels to “Floors” in the menu (0.09 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:52.17 | 2804 | 🖱 click | cursor travels to “Add record” (0.12 s), then clicks *(×4)* | 19 / 0 / 0 |
| 1:52.36 | 2808 | ✎ data write | create Tasks#t8 { title: “Final clean”, status: To do, assignee: Ana, start: Oct 14, duration: 1 d, depends_on: [Floors] } *(×4)* | 20 / 0 / 0 |

**State at the end of chapter 5:** counters local 20 · jev 0 · large 0.

## 6 · Use what exists: drop Tasks  (1:53.62 – 2:13.58 · frames 2840–3338)

> **Caption:** The engine lists every installed component Tasks fits, by structure. Board 1.30, Table 1.15, List 1.15: no blanks, but Board leads by less than 0.25, so jev is asked. It picks Board.

### Underneath

**Drop on the canvas.** Dropping a collection runs `enumerate('Tasks')` (spec §2.2), and every installed component with cardinality *many* is tried:
- **Board** needs `group: Enum (role group)` and `title: Text (role title)`. Both match exactly. The score is:
  - mean fit 1.0;
  - + 0.05 × 2 bound;
  - − 0;
  - + 0.5 × coverage (2 of 5);
  - = **1.30**.
- **Table** and **List** need `title` only: 1.0 + 0.05 + 0.5 × 1/5 = **1.15**.
- **Map** needs a Place field, which Tasks doesn't have. It is listed for transparency with score 0, “not installed”.

`decide()`:
- There are no blanks, but the margin is 0.15, which is below 0.25. So the model is not skipped, and **jev** gets a `DecisionRequest` with the three candidates.
- jev returns `{pick: "Board"}`. `validate()` confirms Board was offered, and the result is cached.
- jev ×1: 180 ms, 14 tokens.

**Place.** Placing the Board is local: columns come from the enum values in order, and there is one card per record.

**Drop a field on a card.** Dropping the `assignee` chip *on a card* is an **explicit target**, so no decision is needed: `card.line2 ← assignee`, applied to every card.

**Drag a card.** Dragging Electrical to Done writes on release:
- `Tasks#t3.status = Done` is one undoable step.
- It's allowed because `status` is writable and the board's group handle is the inverse of `group ← status`.

**Undo.** Ctrl Z (or the Undo button) restores the previous value. The undo is logged as local.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 1:56.28 | 2906 | 🖱 move | cursor → the Tasks collection in the palette | 20 / 0 / 0 |
| 1:56.87 | 2921 | 🖱 press + drag | press on the Tasks collection in the palette and drag “Tasks · 8” to the empty canvas | 20 / 0 / 0 |
| 1:58.27 | 2956 | 🖱 release | release over the empty canvas | 20 / 0 / 0 |
| 1:58.55 | 2963 | ↳ underneath | enumerate(Tasks): Board binds group ← status (exact) and title ← title (exact); Table and List bind title only. Coverage: Board shows 2 of Tasks’ 5 role fields. Scores = mean fit + 0.05×bound − 0.05×blanks + 0.5×coverage | 20 / 0 / 0 |
| 1:58.55 | 2963 | ▤ decision panel | drag · Tasks → canvas → candidates: Board · group ← status 1.30 ✓ · Table 1.15 · List 1.15 · Map 0.00 (not installed) | 20 / 0 / 0 |
| 1:58.92 | 2973 | ◆ jev | drop Tasks → Board · 180 ms · 14 tok | 20 / 1 / 0 |
| 1:58.92 | 2973 | 👁 screen | a Board titled Tasks appears: columns To do (4), Doing (2), Done (2), one card per task | 20 / 1 / 0 |
| 1:58.92 | 2973 | ⚙ local | place Board ← Tasks | 21 / 1 / 0 |
| 2:02.00 | 3050 | 🖱 move | cursor → the assignee chip under Tasks | 21 / 1 / 0 |
| 2:02.59 | 3064 | 🖱 press + drag | press on the assignee chip under Tasks and drag “Task.assignee” to the “Demo walls” card | 21 / 1 / 0 |
| 2:03.78 | 3094 | 🖱 release | release over the “Demo walls” card | 21 / 1 / 0 |
| 2:04.06 | 3101 | 👁 screen | every card gains a second line with the assignee’s name | 21 / 1 / 0 |
| 2:04.06 | 3101 | ⚙ local | card line 2 ← assignee · explicit target, no decision | 22 / 1 / 0 |
| 2:05.74 | 3143 | 🖱 move | cursor → the “Electrical” card | 22 / 1 / 0 |
| 2:06.37 | 3159 | 🖱 press + drag | press and drag the card to the Done column | 22 / 1 / 0 |
| 2:07.98 | 3199 | 🖱 release | release over Done | 22 / 1 / 0 |
| 2:08.33 | 3208 | ✎ data write | Tasks#t3.status = Done (board drag) | 23 / 1 / 0 |
| 2:09.59 | 3239 | 🖱 click | cursor travels to Undo (0.56 s), then clicks | 23 / 1 / 0 |
| 2:10.43 | 3260 | ⌨ key | keycap overlay “Ctrl Z” appears for 1 s: the keyboard equivalent of the Undo click (one undo, not two) | 23 / 1 / 0 |
| 2:11.90 | 3297 | ⚙ local | undo · Tasks#t3.status = Doing | 24 / 1 / 0 |
| 2:11.90 | 3297 | 👁 screen | Electrical slides back to Doing; the column counts return to 4 · 2 · 2 | 24 / 1 / 0 |

**State at the end of chapter 6:** counters local 24 · jev 1 · large 0.

## 7 · Static, from a source, or input  (2:13.58 – 2:41.09 · frames 3339–4026)

> **Caption:** A heading you type is static. A subtitle starting with “=” is live from the namespace. A bar’s width can come from data: drop status on it and jev fills the one blank.

### Underneath

**Heading.** A text atom with typed words is **static**.

**Subtitle.** A text atom whose content starts with `=` is parsed locally as a formula over the namespace, so it is **from a source**. It re-evaluates on every change: “8 tasks · 2 done · 2 in progress”.

**Bar.**
- A rect atom has static width (96 px).
- Dropping the `status` chip on it offers exactly one template, `width = share(Tasks where status = ?)`. The one blank is which value.
- jev ranks the three enum values and picks **Done** (120 ms, 6 tokens).
- The fill-in-the-blank stays visible until you confirm it with ✓.
- The width is now **from a source**, so it animates when the data changes.

**Edit form.**
- The prompt “form to edit the selected task” goes to jev with three engine-built options. It picks **Form · edit · ← board.selection**.
- The form’s *task* property is **from a source**, and that source is a screen variable (`board.selection`). Elements reference elements exactly as they reference data.
- Each field shows its write target, e.g. `→ Task.status`. Those are **inputs**.
- Selecting Drywall fills the form. Choosing Doing and clicking Save writes `Tasks#t5.status = Doing`.
- The board card moves, the subtitle updates, and the bar recomputes.

The scores for the bar blank and the form choice are illustrative. They are spec §2.6 operation templates, not yet in the prototype.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 2:16.24 | 3406 | 🖱 click | cursor travels to the text atom in the palette (0.70 s), then clicks | 24 / 1 / 0 |
| 2:17.22 | 3430 | 🖱 click | cursor travels to a point on the canvas (0.56 s), then clicks | 24 / 1 / 0 |
| 2:18.06 | 3451 | ⌨ type | types “Kitchen renovation” into the new text atom (18 keys) | 24 / 1 / 0 |
| 2:19.21 | 3480 | ▤ inspector | heading (text): text = static · “Kitchen renovation” | 24 / 1 / 0 |
| 2:19.21 | 3480 | ⚙ local | text atom · static | 25 / 1 / 0 |
| 2:19.21 | 3480 | 🖱 click | cursor travels to the text atom in the palette (0.70 s), then clicks | 25 / 1 / 0 |
| 2:20.19 | 3504 | 🖱 click | cursor travels to a point on the canvas (0.49 s), then clicks | 25 / 1 / 0 |
| 2:20.96 | 3523 | ⌨ type | types “= count(Tasks) · count(status = Done) · count(status = Doing)” into the second text atom (61 keys) | 25 / 1 / 0 |
| 2:23.33 | 3583 | ▤ inspector | subtitle (text): text = source · count(Tasks), count(status=…) | 25 / 1 / 0 |
| 2:23.33 | 3583 | ⚙ local | “=” text parsed locally → live source | 26 / 1 / 0 |
| 2:23.33 | 3583 | 👁 screen | the formula is replaced by its live value: “8 tasks · 2 done · 2 in progress” | 26 / 1 / 0 |
| 2:23.33 | 3583 | 🖱 click | cursor travels to the rect atom in the palette (0.70 s), then clicks | 26 / 1 / 0 |
| 2:24.31 | 3607 | 🖱 click | cursor travels to a point on the canvas (0.49 s), then clicks | 26 / 1 / 0 |
| 2:25.78 | 3644 | ▤ inspector | bar (rect): width = static · 96 px \| fill = static · green | 26 / 1 / 0 |
| 2:25.78 | 3644 | 🖱 move | cursor → the status chip under Tasks | 26 / 1 / 0 |
| 2:26.37 | 3659 | 🖱 press + drag | press on the status chip under Tasks and drag “Task.status” to the thin bar | 26 / 1 / 0 |
| 2:27.56 | 3688 | 🖱 release | release over the thin bar | 26 / 1 / 0 |
| 2:27.84 | 3695 | ↳ underneath | dropping an Enum field on a width offers one template: width = share(C where f = ?). The blank is which value. jev ranks the three values | 26 / 1 / 0 |
| 2:27.84 | 3695 | ▤ decision panel | drop · status → bar.width → candidates: share where status = Done 0.81 ✓ · … = Doing 0.42 · … = To do 0.30 | 26 / 1 / 0 |
| 2:28.12 | 3702 | ◆ jev | bar.width ← share(status = Done) · 120 ms · 6 tok | 26 / 2 / 0 |
| 2:28.82 | 3720 | 🖱 click | cursor travels to confirm the fill-in (0.49 s), then clicks | 26 / 2 / 0 |
| 2:29.59 | 3739 | ▤ inspector | bar (rect): width = source · share(Tasks, status = Done) \| fill = static · green | 26 / 2 / 0 |
| 2:29.59 | 3739 | 👁 screen | the bar fills to 25% (2 of 8 done) | 26 / 2 / 0 |
| 2:30.99 | 3774 | 🖱 click | cursor travels to the Ask bar (0.63 s), then clicks | 26 / 2 / 0 |
| 2:31.90 | 3797 | ⌨ type | types “form to edit the selected task” into the Ask bar (30 keys) | 26 / 2 / 0 |
| 2:33.51 | 3837 | ⌨ key | presses Enter · submit the prompt | 26 / 2 / 0 |
| 2:34.49 | 3862 | ▤ decision panel | prompt · form to edit the selected task → candidates: Form · edit · ← board.selection 0.92 ✓ · Form · create new Task 0.61 · Table row editor 0.44 | 26 / 2 / 0 |
| 2:34.93 | 3873 | ◆ jev | Form ← board.selection · save → update Task · 210 ms · 24 tok | 26 / 3 / 0 |
| 2:34.93 | 3873 | ▤ inspector | form (frame): task = source · board.selection \| fields = input · → Task.title, status, assignee, start \| save = input · → update Task | 26 / 3 / 0 |
| 2:34.93 | 3873 | 🖱 click | cursor travels to the “Drywall” card (0.63 s), then clicks | 26 / 3 / 0 |
| 2:35.84 | 3896 | ⚙ local | board.selection = Tasks#t5 → form fills | 27 / 3 / 0 |
| 2:35.84 | 3896 | 🖱 click | cursor travels to the status field in the Edit task form (0.56 s), then clicks | 27 / 3 / 0 |
| 2:37.03 | 3925 | 🖱 click | cursor travels to “Doing” in the menu (0.35 s), then clicks | 27 / 3 / 0 |
| 2:37.66 | 3941 | 🖱 click | cursor travels to the form’s Save button (0.56 s), then clicks | 27 / 3 / 0 |
| 2:39.13 | 3978 | ✎ data write | Tasks#t5.status = Doing (form save) | 28 / 3 / 0 |
| 2:39.13 | 3978 | 👁 screen | Drywall moves from To do to Doing; the subtitle now says 3 in progress | 28 / 3 / 0 |

**State at the end of chapter 7:** counters local 28 · jev 3 · large 0.

## 8 · Ask for something nothing draws  (2:41.09 – 2:51.17 · frames 4027–4278)

> **Caption:** “tasks over time, one row per person.” No installed component consumes start + duration with a row. The engine finds zero candidates, so no model is called and a hole appears.

### Underneath

- **Parsing the prompt (local).** “tasks” matches the collection Tasks, and “over time” sets `temporal = true`.
- **Enumeration.** `enumerate('Tasks', {temporal: true})` keeps only components whose contract is temporal. None is installed, so the candidate list is empty.
- **Deciding.** `decide()` with zero live candidates returns `none` **without calling jev**, and the decision panel says “local · 2 ms”.
- **The hole.** The engine places a hole that states the needed shape (start, duration, a row per value) and offers two ways forward:
  - open the maker, pre-loaded with Tasks’ fields;
  - Retry.
- **No fallback.** Nothing is forced, and no table appears.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 2:43.75 | 4093 | 🖱 click | cursor travels to the Ask bar (0.63 s), then clicks | 28 / 3 / 0 |
| 2:44.66 | 4116 | ⌨ type | types “tasks over time, one row per person” into the Ask bar (35 keys) | 28 / 3 / 0 |
| 2:46.55 | 4163 | ⌨ key | presses Enter · submit the prompt | 28 / 3 / 0 |
| 2:47.53 | 4188 | ↳ underneath | the prompt is parsed locally: “tasks” names the collection, “over time” sets the temporal flag. enumerate(Tasks, temporal) returns zero candidates (none of Board/Table/List/Form/Dial is temporal), so decide() returns none locally | 28 / 3 / 0 |
| 2:47.53 | 4188 | ▤ decision panel | prompt · tasks over time, one row per person → candidates: (no temporal component installed) 0.00 (not installed) | 28 / 3 / 0 |
| 2:47.81 | 4195 | ⚙ local | no candidates → hole (no model call) | 29 / 3 / 0 |
| 2:47.81 | 4195 | 👁 screen | a dashed orange hole fills the bottom of the canvas: “? Tasks over time, one row per person”, with Open component maker and Retry | 29 / 3 / 0 |

**State at the end of chapter 8:** counters local 29 · jev 3 · large 0.

## 9 · Build it from atoms  (2:51.17 – 3:05.63 · frames 4279–4639)

> **Caption:** Open the maker from the hole: Tasks’ fields arrive as chips. A line plus a date label is a time axis; a rectangle on it is the bar. All local.

### Underneath

- **Opening the maker.** Clicking “Open component maker” in the hole opens the maker with the hole's data (Tasks) as field chips: title, start, duration, assignee, status.
- **Time axis.** A **line** atom plus a **text** atom reading “Oct 1 — Oct 14” is parsed locally as a time scale: 14 days, 1 day = 34 px. The ticks appear.
- **Item template.** A **rect** drawn on the axis becomes the item template, repeated once per record.
- Everything in this chapter is local.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 2:53.83 | 4345 | 🖱 click | cursor travels to “Open component maker” in the hole (0.70 s), then clicks | 29 / 3 / 0 |
| 2:54.81 | 4370 | 👁 screen | switches to the Component maker tab | 29 / 3 / 0 |
| 2:54.81 | 4370 | ⚙ local | maker opened · chips from Tasks | 30 / 3 / 0 |
| 2:56.07 | 4401 | 🖱 click | cursor travels to the line atom in the palette (0.70 s), then clicks | 30 / 3 / 0 |
| 2:57.05 | 4426 | 🖱 click | cursor travels to the stage (0.63 s), then clicks | 30 / 3 / 0 |
| 2:57.96 | 4448 | 🖱 press + drag | drags right 480 px to draw the line | 30 / 3 / 0 |
| 2:58.94 | 4473 | 🖱 click | cursor travels to the text atom in the palette (0.70 s), then clicks | 30 / 3 / 0 |
| 2:59.92 | 4497 | 🖱 click | cursor travels to above the line (0.56 s), then clicks | 30 / 3 / 0 |
| 3:00.76 | 4518 | ⌨ type | types “Oct 1 — Oct 14” into the label (14 keys) | 30 / 3 / 0 |
| 3:01.85 | 4546 | ⚙ local | date label parsed → time scale | 31 / 3 / 0 |
| 3:01.85 | 4546 | 🖱 click | cursor travels to the rect atom in the palette (0.70 s), then clicks | 31 / 3 / 0 |
| 3:02.83 | 4570 | 🖱 click | cursor travels to under the axis at Oct 4 (0.56 s), then clicks | 31 / 3 / 0 |
| 3:03.67 | 4591 | 🖱 press + drag | drags to draw the rectangle 4 days wide | 31 / 3 / 0 |
| 3:04.51 | 4612 | ⚙ local | rect on the axis → item template | 32 / 3 / 0 |

**State at the end of chapter 9:** counters local 32 · jev 3 · large 0.

## 10 · Map fields onto the shape itself  (3:05.63 – 3:24.81 · frames 4640–5119)

> **Caption:** start on the left edge, duration on the width, assignee on the row, title on the bar, status on the fill. The contract grows with each drop; the preview uses a sandbox copy.

### Underneath

Each chip drop creates an **encoding** (`shape property ← field`) and grows the contract’s CONSUMES as a structural type:
- `x ← start`, `width ← duration` (days → px), `row ← assignee` (group-by into rows), `text ← title`, `fill ← status` (enum → palette).

The **live preview** renders the real 8 tasks from a **sandbox copy**. Dragging inside the preview never writes real data.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 3:08.29 | 4707 | 🖱 move | cursor → the start chip | 32 / 3 / 0 |
| 3:08.88 | 4721 | 🖱 press + drag | press on the start chip and drag “Task.start” to the bar’s left edge | 32 / 3 / 0 |
| 3:10.00 | 4749 | 🖱 release | release over the bar’s left edge | 32 / 3 / 0 |
| 3:10.28 | 4756 | ⚙ local | map x ← start | 33 / 3 / 0 |
| 3:10.28 | 4756 | ▤ contract card | CONSUMES = Many | 33 / 3 / 0 |
| 3:11.25 | 4781 | 🖱 move | cursor → the duration chip | 33 / 3 / 0 |
| 3:11.84 | 4796 | 🖱 press + drag | press on the duration chip and drag “Task.duration” to the bar’s width | 33 / 3 / 0 |
| 3:12.96 | 4824 | 🖱 release | release over the bar’s width | 33 / 3 / 0 |
| 3:13.24 | 4831 | ⚙ local | map width ← duration | 34 / 3 / 0 |
| 3:13.24 | 4831 | ▤ contract card | CONSUMES = Many | 34 / 3 / 0 |
| 3:14.22 | 4855 | 🖱 move | cursor → the assignee chip | 34 / 3 / 0 |
| 3:14.81 | 4870 | 🖱 press + drag | press on the assignee chip and drag “Task.assignee” to the row slot left of the bar | 34 / 3 / 0 |
| 3:15.93 | 4898 | 🖱 release | release over the row slot left of the bar | 34 / 3 / 0 |
| 3:16.21 | 4905 | ⚙ local | map row ← assignee | 35 / 3 / 0 |
| 3:16.21 | 4905 | ▤ contract card | CONSUMES = Many | 35 / 3 / 0 |
| 3:17.19 | 4929 | 🖱 move | cursor → the title chip | 35 / 3 / 0 |
| 3:17.78 | 4944 | 🖱 press + drag | press on the title chip and drag “Task.title” to the middle of the bar | 35 / 3 / 0 |
| 3:18.90 | 4972 | 🖱 release | release over the middle of the bar | 35 / 3 / 0 |
| 3:19.18 | 4979 | ⚙ local | map text ← title | 36 / 3 / 0 |
| 3:19.18 | 4979 | ▤ contract card | CONSUMES = Many | 36 / 3 / 0 |
| 3:20.16 | 5003 | 🖱 move | cursor → the status chip | 36 / 3 / 0 |
| 3:20.75 | 5018 | 🖱 press + drag | press on the status chip and drag “Task.status” to the bar’s fill | 36 / 3 / 0 |
| 3:21.87 | 5046 | 🖱 release | release over the bar’s fill | 36 / 3 / 0 |
| 3:22.15 | 5053 | ⚙ local | map fill ← status | 37 / 3 / 0 |
| 3:22.15 | 5053 | ▤ contract card | CONSUMES = Many | 37 / 3 / 0 |
| 3:23.13 | 5078 | 👁 screen | the live preview now shows all 8 tasks as coloured bars in rows Ana, Sam, Lee | 37 / 3 / 0 |

**State at the end of chapter 10:** counters local 37 · jev 3 · large 0.

## 11 · Handles, a rule, ports, and one new function  (3:24.81 – 3:48.45 · frames 5120–5710)

> **Caption:** Handles are encodings run backwards: end → duration, body → start. × means no overlap in a row. A note asks for new logic: jev escalates, the large model writes one pure function, checks pass.

### Underneath

**Handles.** Handles are **inverse encodings**, and they exist only because the mapped fields are writable:
- end → `duration` (snap 1 day);
- body → `start`.

**Rule.** The **×** text becomes the rule `no_overlap(row, [start, start+duration))`, enforced by the engine during every drag.

**Ports.**
- in: `Many<{start, duration, row, title?, fill?}>`;
- out: `moved`, `resized`, `selection`.

**The note** “red if it would delay the finish”:
- jev is asked to map the note to an existing operation template. None computes slack over `depends_on`, so jev returns **escalate** with the signature `critical(task, all) → Bool` (140 ms, 9 tokens).
- The **large model** writes one pure function (1.8 s, 212 tokens).
- `checkFoil` then runs:
  - **purity:** no globals, no writes into inputs; writes into its own locals are allowed;
  - **type:** Bool;
  - **inputs unchanged** after every run;
  - **edge cases**;
  - **isolated eval** on all 8 records.
- On pass, the function is stored and runs natively, and the fill becomes `critical ? red : status`.
- On fail, the previous fill is kept and a hole explains why. The prototype test S11 covers this path; the video shows the pass.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 3:27.47 | 5186 | 🖱 click | cursor travels to the bar’s right end (0.70 s), then clicks | 37 / 3 / 0 |
| 3:30.69 | 5267 | ⚙ local | handle end → duration (inverse of width) · writable ✓ | 38 / 3 / 0 |
| 3:30.69 | 5267 | 🖱 click | cursor travels to the bar’s body (0.70 s), then clicks | 38 / 3 / 0 |
| 3:31.67 | 5291 | ⚙ local | handle body → start (inverse of x) | 39 / 3 / 0 |
| 3:31.67 | 5291 | ▤ contract card | HANDLES = end → duration · body → start · snap 1 day | 39 / 3 / 0 |
| 3:31.67 | 5291 | 🖱 click | cursor travels to the text atom in the palette (0.70 s), then clicks | 39 / 3 / 0 |
| 3:32.65 | 5316 | 🖱 click | cursor travels to next to the bar (0.56 s), then clicks | 39 / 3 / 0 |
| 3:33.49 | 5337 | ⌨ type | types “×” into the stage (1 keys) | 39 / 3 / 0 |
| 3:33.84 | 5345 | ⚙ local | × → rule no_overlap(row, [start, start+duration)) | 40 / 3 / 0 |
| 3:33.84 | 5345 | ▤ contract card | RULES = no_overlap(row, interval) | 40 / 3 / 0 |
| 3:33.84 | 5345 | 🖱 press + drag | pulls a port out of the left edge | 40 / 3 / 0 |
| 3:34.68 | 5366 | 🖱 press + drag | pulls a port out of the right edge | 40 / 3 / 0 |
| 3:35.52 | 5387 | ⚙ local | ports: 1 in, 3 out | 41 / 3 / 0 |
| 3:35.52 | 5387 | ▤ contract card | PRODUCES = moved · resized · selection | 41 / 3 / 0 |
| 3:37.48 | 5436 | 🖱 click | cursor travels to under the bar (0.56 s), then clicks | 41 / 3 / 0 |
| 3:38.32 | 5457 | ⌨ type | types “red if it would delay the finish” into a note on the bar (32 keys) | 41 / 3 / 0 |
| 3:40.04 | 5501 | ▤ decision panel | note · red if it would delay the finish → candidates: template: filter on a field 0.12 · template: count(…) ≤ n 0.08 · escalate: new function needed 0.94 ✓ | 41 / 3 / 0 |
| 3:40.33 | 5508 | ◆ jev | note → escalate · 140 ms · 9 tok | 41 / 4 / 0 |
| 3:41.17 | 5529 | ◆◆ large model | authored critical(task, all) · 1.8 s · 212 tok | 41 / 4 / 1 |
| 3:43.69 | 5592 | ⚙ local | checkFoil passed · stored · runs natively | 42 / 4 / 1 |
| 3:46.21 | 5655 | ▤ contract card | DERIVED = fill ← critical ? red : status | 42 / 4 / 1 |
| 3:46.21 | 5655 | 👁 screen | preview: the critical path (Demo walls, Electrical, Plumbing, Drywall, Paint, Floors, Final clean) turns red; Order fixtures keeps its status colour | 42 / 4 / 1 |

**State at the end of chapter 11:** counters local 42 · jev 4 · large 1.

## 12 · Save it. The hole resolves. Use it.  (3:48.45 – 4:12.94 · frames 5711–6322)

> **Caption:** Saved, it is a candidate like any other. Retry: Timeline lane is the only temporal candidate, but row is a blank, so jev fills it. Then drag: an end writes duration, an overlap is refused.

### Underneath

**Save.** Saving registers **Timeline lane v1** in the registry and the palette.

**Retry.**
- Retry runs `enumerate('Tasks', {temporal: true})` again. Now there is exactly one candidate, Timeline lane, scoring **1.60** with one blank: `row` matched assignee by type only, because a Ref is not a declared row role.
- One blank means the model can't be skipped, so jev fills it with `row = assignee` (150 ms, 11 tokens).
- The hole is replaced by **Schedule**.

**Selection.** Clicking Electrical sets `selection = Tasks#t3`. The board highlights the same record, because selection is shared by record id. Nothing is written.

**End handle.**
- Dragging Plumbing’s end one day right writes `Tasks#t4.duration = 4` on release.
- `critical()` re-runs natively. Electrical now has 1 day of slack, so it loses its red.

**Rule.**
- Dragging Paint left over Electrical (both in Sam’s row) shows the **violation** outline while overlapping.
- On release the move is **rejected**: it snaps back and **nothing is written**.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 3:51.11 | 5777 | 🖱 click | cursor travels to the component name box (0.70 s), then clicks | 42 / 4 / 1 |
| 3:52.09 | 5802 | ⌨ type | types “Timeline lane” into the component name box (13 keys) | 42 / 4 / 1 |
| 3:53.23 | 5830 | ▤ contract card | VERSION = v1 | 42 / 4 / 1 |
| 3:53.23 | 5830 | 🖱 click | cursor travels to “Save to palette” (0.70 s), then clicks | 42 / 4 / 1 |
| 3:54.21 | 5855 | ⚙ local | saved Timeline lane v1 → palette | 43 / 4 / 1 |
| 3:54.21 | 5855 | 👁 screen | switches to the Renovation job canvas | 43 / 4 / 1 |
| 3:56.73 | 5918 | 🖱 click | cursor travels to “Retry” in the hole (0.70 s), then clicks | 43 / 4 / 1 |
| 3:57.71 | 5942 | ▤ decision panel | retry hole · Tasks over time → candidates: Timeline lane v1 · 1 blank 1.60 ✓ | 43 / 4 / 1 |
| 3:58.03 | 5950 | ◆ jev | hole → Timeline lane · row = assignee · 150 ms · 11 tok | 43 / 5 / 1 |
| 3:58.03 | 5950 | ⚙ local | place Timeline lane ← Tasks | 44 / 5 / 1 |
| 3:58.03 | 5950 | 👁 screen | the hole is replaced by “Schedule”: 8 bars in rows Ana, Sam, Lee, critical ones red | 44 / 5 / 1 |
| 4:00.27 | 6006 | 🖱 click | cursor travels to the Electrical bar (0.63 s), then clicks | 44 / 5 / 1 |
| 4:01.18 | 6029 | ⚙ local | selection = Tasks#t3 → board card highlighted too | 45 / 5 / 1 |
| 4:01.18 | 6029 | 👁 screen | Electrical is outlined blue in the schedule and on the board | 45 / 5 / 1 |
| 4:03.00 | 6074 | 🖱 move | cursor → the right end of the Plumbing bar | 45 / 5 / 1 |
| 4:03.63 | 6090 | 🖱 press + drag | press on the end handle and drag right one day | 45 / 5 / 1 |
| 4:05.17 | 6129 | 🖱 release | release (snapped to 4 days) | 45 / 5 / 1 |
| 4:05.17 | 6129 | ✎ data write | Tasks#t4.duration = 4 d (end handle) | 46 / 5 / 1 |
| 4:05.17 | 6129 | ⚙ local | critical() re-ran natively · Electrical no longer critical | 47 / 5 / 1 |
| 4:05.17 | 6129 | 👁 screen | Plumbing is now 4 days; Electrical turns from red to its status colour because it now has 1 day of slack | 47 / 5 / 1 |
| 4:07.41 | 6185 | 🖱 move | cursor → the middle of the Paint bar | 47 / 5 / 1 |
| 4:08.04 | 6200 | 🖱 press + drag | press on the Paint body and drag left five days, over Electrical | 47 / 5 / 1 |
| 4:10.00 | 6249 | 👁 screen | while overlapping Electrical, the Paint bar gets a dashed red outline | 47 / 5 / 1 |
| 4:10.70 | 6267 | 🖱 release | release over Electrical | 47 / 5 / 1 |
| 4:11.26 | 6281 | ⚙ local | rejected by rule no_overlap(Sam) · nothing written | 48 / 5 / 1 |
| 4:11.26 | 6281 | 👁 screen | Paint snaps back to Oct 9; nothing was written | 48 / 5 / 1 |

**State at the end of chapter 12:** counters local 48 · jev 5 · large 1.

## 13 · Different data, same component  (4:12.94 – 4:51.39 · frames 6323–7283)

> **Caption:** A new collection, Bookings: who, room, from, to. No start, no duration. Dropped, Timeline lane still fits by structure: start ← from, duration ← to − from (adapter), row ← room (blank).

### Underneath

**Schema.** `Bookings : Many<Booking{who: Text(title), room: Enum(group), from: Date(start), to: Date(end)}>`. The schema and four records are entered at ×2.

**Matching on drop.**
- `start ← from` is exact: `from` carries role start.
- `duration ← to − from` comes from the registered **adapter** end-minus-start, scored 0.8 and counted as a blank.
- `row ← room` is a type match, so it's a blank.
- `title ← who` is exact.
- Coverage is 4 of 4. The score is **1.43**, ahead of Board (1.35), which would drop the time interval.
- jev fills the two blanks (150 ms, 12 tokens). The fill-in-the-blank shows them.

**Dragging Painter.** Dragging the Painter bar one day right writes **both** `from` and `to`, because the adapter’s inverse is known. Moving shifts both; resizing would change only `to`.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 4:15.60 | 6389 | 🖱 click | cursor travels to “+ New collection” in the palette (0.70 s), then clicks | 48 / 5 / 1 |
| 4:16.58 | 6414 | 🖱 click | cursor travels to the collection Name box (0.35 s), then clicks *(×2)* | 48 / 5 / 1 |
| 4:17.07 | 6426 | ⌨ type | types “Bookings” into the Name box (8 keys) *(×2)* | 48 / 5 / 1 |
| 4:17.38 | 6434 | 🖱 click | cursor travels to “+ field” (0.28 s), then clicks *(×2)* | 48 / 5 / 1 |
| 4:17.80 | 6444 | 🖱 click | cursor travels to the field-name box on row 1 (0.24 s), then clicks *(×2)* | 48 / 5 / 1 |
| 4:18.18 | 6454 | ⌨ type | types “who” into field name 1 (3 keys) *(×2)* | 48 / 5 / 1 |
| 4:18.29 | 6457 | 🖱 click | cursor travels to the type box on row 1 (0.24 s), then clicks *(×2)* | 48 / 5 / 1 |
| 4:18.85 | 6471 | 🖱 click | cursor travels to “Text” in the menu (0.21 s), then clicks *(×2)* | 48 / 5 / 1 |
| 4:19.28 | 6482 | 👁 screen | row 1 now reads: who : Text · role title · writable *(×2)* | 48 / 5 / 1 |
| 4:19.28 | 6482 | ⚙ local | who: Text → role title (inferRole) *(×2)* | 49 / 5 / 1 |
| 4:19.28 | 6482 | 🖱 click | cursor travels to “+ field” (0.28 s), then clicks *(×2)* | 49 / 5 / 1 |
| 4:19.70 | 6492 | 🖱 click | cursor travels to the field-name box on row 2 (0.24 s), then clicks *(×2)* | 49 / 5 / 1 |
| 4:20.09 | 6502 | ⌨ type | types “room” into field name 2 (4 keys) *(×2)* | 49 / 5 / 1 |
| 4:20.23 | 6505 | 🖱 click | cursor travels to the type box on row 2 (0.24 s), then clicks *(×2)* | 49 / 5 / 1 |
| 4:20.79 | 6519 | 🖱 click | cursor travels to “Enum…” in the menu (0.21 s), then clicks *(×2)* | 49 / 5 / 1 |
| 4:21.22 | 6530 | ⌨ type | types “Kitchen” into the enum values box (7 keys) *(×2)* | 49 / 5 / 1 |
| 4:21.49 | 6537 | ⌨ key | presses Enter · value “Kitchen” becomes a chip *(×2)* | 49 / 5 / 1 |
| 4:21.98 | 6549 | ⌨ type | types “Pantry” into the enum values box (6 keys) *(×2)* | 49 / 5 / 1 |
| 4:22.22 | 6555 | ⌨ key | presses Enter · value “Pantry” becomes a chip *(×2)* | 49 / 5 / 1 |
| 4:22.71 | 6567 | ⌨ type | types “Dining” into the enum values box (6 keys) *(×2)* | 49 / 5 / 1 |
| 4:22.94 | 6573 | ⌨ key | presses Enter · value “Dining” becomes a chip *(×2)* | 49 / 5 / 1 |
| 4:23.64 | 6591 | 👁 screen | row 2 now reads: room : Enum · Kitchen, Pantry, Dining · role group · writable *(×2)* | 49 / 5 / 1 |
| 4:23.64 | 6591 | ⚙ local | room: Enum · Kitchen, Pantry, Dining → role group (inferRole) *(×2)* | 50 / 5 / 1 |
| 4:23.64 | 6591 | 🖱 click | cursor travels to “+ field” (0.28 s), then clicks *(×2)* | 50 / 5 / 1 |
| 4:24.06 | 6601 | 🖱 click | cursor travels to the field-name box on row 3 (0.24 s), then clicks *(×2)* | 50 / 5 / 1 |
| 4:24.44 | 6611 | ⌨ type | types “from” into field name 3 (4 keys) *(×2)* | 50 / 5 / 1 |
| 4:24.58 | 6614 | 🖱 click | cursor travels to the type box on row 3 (0.24 s), then clicks *(×2)* | 50 / 5 / 1 |
| 4:25.14 | 6628 | 🖱 click | cursor travels to “Date” in the menu (0.21 s), then clicks *(×2)* | 50 / 5 / 1 |
| 4:25.58 | 6639 | 👁 screen | row 3 now reads: from : Date · role start · writable *(×2)* | 50 / 5 / 1 |
| 4:25.58 | 6639 | ⚙ local | from: Date → role start (inferRole) *(×2)* | 51 / 5 / 1 |
| 4:25.58 | 6639 | 🖱 click | cursor travels to “+ field” (0.28 s), then clicks *(×2)* | 51 / 5 / 1 |
| 4:26.00 | 6649 | 🖱 click | cursor travels to the field-name box on row 4 (0.24 s), then clicks *(×2)* | 51 / 5 / 1 |
| 4:26.38 | 6659 | ⌨ type | types “to” into field name 4 (2 keys) *(×2)* | 51 / 5 / 1 |
| 4:26.45 | 6661 | 🖱 click | cursor travels to the type box on row 4 (0.24 s), then clicks *(×2)* | 51 / 5 / 1 |
| 4:27.01 | 6675 | 🖱 click | cursor travels to “Date” in the menu (0.21 s), then clicks *(×2)* | 51 / 5 / 1 |
| 4:27.45 | 6686 | 👁 screen | row 4 now reads: to : Date · role end · writable *(×2)* | 51 / 5 / 1 |
| 4:27.45 | 6686 | ⚙ local | to: Date → role end (inferRole) *(×2)* | 52 / 5 / 1 |
| 4:27.45 | 6686 | 🖱 click | cursor travels to “Create collection” (0.32 s), then clicks *(×2)* | 52 / 5 / 1 |
| 4:27.90 | 6697 | 👁 screen | the editor closes; “Bookings” appears under Namespace · data with its field chips *(×2)* | 52 / 5 / 1 |
| 4:27.90 | 6697 | ⚙ local | + Bookings : Many<Booking> · 4 fields *(×2)* | 53 / 5 / 1 |
| 4:27.90 | 6697 | 🖱 click | cursor travels to the “who” control (0.21 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:28.25 | 6706 | ⌨ type | types “Electrician” into the who input (11 keys) *(×2)* | 53 / 5 / 1 |
| 4:28.60 | 6715 | 🖱 click | cursor travels to “Kitchen” on the room control (0.21 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:28.95 | 6723 | 🖱 click | cursor travels to the “from” control (0.21 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:29.44 | 6736 | 🖱 click | cursor travels to Oct 3 in the date picker (0.21 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:29.86 | 6746 | 🖱 click | cursor travels to the “to” control (0.21 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:30.35 | 6758 | 🖱 click | cursor travels to Oct 6 in the date picker (0.21 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:30.77 | 6769 | 🖱 click | cursor travels to “Add record” (0.24 s), then clicks *(×2)* | 53 / 5 / 1 |
| 4:31.16 | 6778 | ✎ data write | create Bookings#b1 { who: “Electrician”, room: Kitchen, from: Oct 3, to: Oct 6 } *(×2)* | 54 / 5 / 1 |
| 4:31.16 | 6778 | 🖱 click | cursor travels to the “who” control (0.21 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:31.51 | 6787 | ⌨ type | types “Plumber” into the who input (7 keys) *(×2)* | 54 / 5 / 1 |
| 4:31.73 | 6793 | 🖱 click | cursor travels to “Pantry” on the room control (0.21 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:32.08 | 6802 | 🖱 click | cursor travels to the “from” control (0.21 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:32.57 | 6814 | 🖱 click | cursor travels to Oct 3 in the date picker (0.21 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:32.99 | 6824 | 🖱 click | cursor travels to the “to” control (0.21 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:33.48 | 6837 | 🖱 click | cursor travels to Oct 5 in the date picker (0.21 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:33.90 | 6847 | 🖱 click | cursor travels to “Add record” (0.24 s), then clicks *(×2)* | 54 / 5 / 1 |
| 4:34.29 | 6857 | ✎ data write | create Bookings#b2 { who: “Plumber”, room: Pantry, from: Oct 3, to: Oct 5 } *(×2)* | 55 / 5 / 1 |
| 4:34.29 | 6857 | 🖱 click | cursor travels to the “who” control (0.21 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:34.64 | 6865 | ⌨ type | types “Painter” into the who input (7 keys) *(×2)* | 55 / 5 / 1 |
| 4:34.86 | 6871 | 🖱 click | cursor travels to “Dining” on the room control (0.21 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:35.21 | 6880 | 🖱 click | cursor travels to the “from” control (0.21 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:35.70 | 6892 | 🖱 click | cursor travels to Oct 9 in the date picker (0.21 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:36.12 | 6902 | 🖱 click | cursor travels to the “to” control (0.21 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:36.61 | 6915 | 🖱 click | cursor travels to Oct 11 in the date picker (0.21 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:37.03 | 6925 | 🖱 click | cursor travels to “Add record” (0.24 s), then clicks *(×2)* | 55 / 5 / 1 |
| 4:37.41 | 6935 | ✎ data write | create Bookings#b3 { who: “Painter”, room: Dining, from: Oct 9, to: Oct 11 } *(×2)* | 56 / 5 / 1 |
| 4:37.41 | 6935 | 🖱 click | cursor travels to the “who” control (0.21 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:37.76 | 6944 | ⌨ type | types “Tiler” into the who input (5 keys) *(×2)* | 56 / 5 / 1 |
| 4:37.92 | 6948 | 🖱 click | cursor travels to “Kitchen” on the room control (0.21 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:38.27 | 6956 | 🖱 click | cursor travels to the “from” control (0.21 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:38.76 | 6969 | 🖱 click | cursor travels to Oct 10 in the date picker (0.21 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:39.18 | 6979 | 🖱 click | cursor travels to the “to” control (0.21 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:39.67 | 6991 | 🖱 click | cursor travels to Oct 12 in the date picker (0.21 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:40.09 | 7002 | 🖱 click | cursor travels to “Add record” (0.24 s), then clicks *(×2)* | 56 / 5 / 1 |
| 4:40.48 | 7011 | ✎ data write | create Bookings#b4 { who: “Tiler”, room: Kitchen, from: Oct 10, to: Oct 12 } *(×2)* | 57 / 5 / 1 |
| 4:40.48 | 7011 | 👁 screen | the canvas pans right to the second area | 57 / 5 / 1 |
| 4:41.74 | 7043 | 🖱 move | cursor → the Bookings collection in the palette | 57 / 5 / 1 |
| 4:42.32 | 7058 | 🖱 press + drag | press on the Bookings collection in the palette and drag “Bookings · 4” to the empty right-hand area | 57 / 5 / 1 |
| 4:43.73 | 7093 | 🖱 release | release over the empty right-hand area | 57 / 5 / 1 |
| 4:44.00 | 7100 | ↳ underneath | Timeline lane: start ← from (exact role start), duration ← to − from (adapter end-minus-start, 0.8), row ← room (type blank, 0.5), title ← who (exact). Coverage 4/4 → 1.43. Board fits too (group ← room) but shows only 2 of 4 role fields → 1.35 | 57 / 5 / 1 |
| 4:44.00 | 7100 | ▤ decision panel | drag · Bookings → canvas → candidates: Timeline lane v1 · 2 blanks 1.43 ✓ · Board · group ← room 1.35 · Table 1.18 · List 1.18 | 57 / 5 / 1 |
| 4:44.32 | 7108 | ◆ jev | Bookings → Timeline lane · 2 blanks filled · 150 ms · 12 tok | 57 / 6 / 1 |
| 4:44.32 | 7108 | ⚙ local | place Timeline lane ← Bookings | 58 / 6 / 1 |
| 4:47.40 | 7185 | 🖱 move | cursor → the middle of the Painter bar | 58 / 6 / 1 |
| 4:48.03 | 7200 | 🖱 press + drag | press on the Painter body and drag right one day | 58 / 6 / 1 |
| 4:49.43 | 7235 | 🖱 release | release | 58 / 6 / 1 |
| 4:49.43 | 7235 | ✎ data write | Bookings#b3.from = Oct 10, .to = Oct 12 (adapter inverse: move shifts both) | 59 / 6 / 1 |
| 4:49.43 | 7235 | 👁 screen | Painter now spans Oct 10–12; the record’s from and to both changed | 59 / 6 / 1 |

**State at the end of chapter 13:** counters local 59 · jev 6 · large 1.

## 14 · Read-only data, and changing a component once  (4:51.39 – 5:20.85 · frames 7284–8020)

> **Caption:** A sensor stream connects with its fields locked. Dropped, it becomes a Dial: the needle can’t be dragged; the target can. Then Timeline lane gets rounder corners: v2, both uses update.

### Underneath

**Connecting the stream.**
- “⇢ Connect → Sensor stream” creates `Freezer` with **read-only** fields: label, value, max and limit (🔒, dashed chips).
- `target` is writable, because it's a device setpoint.

**Matching.**
- Dropping Freezer gives exactly one candidate, Dial (1.60), with no blanks. So the decision is **local**: no model.

**Handles.**
- Pressing the needle shows a lock tooltip, “value is read-only (stream) · no handle”, and nothing is written.
- Dragging the target marker writes `Freezer#z1.target = 8.5` (snap 0.5).
- The needle keeps following the live stream.

**New version.**
- Opening Timeline lane from the palette shows it still as atoms.
- Corner radius 4 → 10 and Save make **v2**. Both uses (Schedule and Room bookings) re-render, with their bindings kept.

**Downstream hole.** A **button** atom labelled “Notify crew” has no declared effect, so it shows a downstream hole, “→ ? what does this do”. It never silently does nothing.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 4:54.05 | 7351 | 🖱 click | cursor travels to “⇢ Connect” in the palette (0.70 s), then clicks | 59 / 6 / 1 |
| 4:55.45 | 7386 | 🖱 click | cursor travels to “Sensor stream · freezer-s2” in the menu (0.42 s), then clicks | 59 / 6 / 1 |
| 4:56.32 | 7407 | ⚙ local | + Freezer · stream · value, max, limit read-only 🔒 · target writable | 60 / 6 / 1 |
| 4:58.00 | 7449 | 🖱 move | cursor → the Freezer collection in the palette | 60 / 6 / 1 |
| 4:58.59 | 7464 | 🖱 press + drag | press on the Freezer collection in the palette and drag “Freezer · live” to the area under the bookings | 60 / 6 / 1 |
| 4:59.99 | 7499 | 🖱 release | release over the area under the bookings | 60 / 6 / 1 |
| 5:00.27 | 7506 | ▤ decision panel | drag · Freezer → canvas → candidates: Dial · value, max, limit, target 1.60 ✓ | 60 / 6 / 1 |
| 5:00.55 | 7513 | ⚙ local | Freezer → Dial (single candidate, local) | 61 / 6 / 1 |
| 5:00.55 | 7513 | 👁 screen | a Dial shows 6.2 °C, a red band above the 8° limit, and an orange target marker at 7° | 61 / 6 / 1 |
| 5:02.23 | 7555 | 🖱 move | cursor → the needle | 61 / 6 / 1 |
| 5:02.86 | 7571 | 🖱 press + drag | press on the needle and try to drag it | 61 / 6 / 1 |
| 5:03.14 | 7578 | ⚙ local | needle · value read-only → lock, nothing written | 62 / 6 / 1 |
| 5:05.66 | 7641 | 🖱 move | cursor → the orange target marker | 62 / 6 / 1 |
| 5:06.29 | 7657 | 🖱 press + drag | press on the target marker and drag it clockwise to 8.5° | 62 / 6 / 1 |
| 5:07.83 | 7695 | 🖱 release | release (snapped to 0.5°) | 62 / 6 / 1 |
| 5:07.83 | 7695 | ✎ data write | Freezer#z1.target = 8.5 °C (dial target handle) | 63 / 6 / 1 |
| 5:09.23 | 7730 | 🖱 click | cursor travels to “Timeline lane v1” in the palette (0.70 s), then clicks | 63 / 6 / 1 |
| 5:10.21 | 7755 | 👁 screen | switches to the Component maker tab | 63 / 6 / 1 |
| 5:10.21 | 7755 | 👁 screen | the maker opens Timeline lane: still its atoms, mappings, handles, rule and function | 63 / 6 / 1 |
| 5:11.47 | 7786 | 🖱 move | cursor → the bar’s corner | 63 / 6 / 1 |
| 5:12.03 | 7800 | 🖱 press + drag | drags the corner-radius handle from 4 to 10 px | 63 / 6 / 1 |
| 5:13.01 | 7825 | ▤ contract card | VERSION = v2 · 2 uses | 63 / 6 / 1 |
| 5:13.01 | 7825 | 🖱 click | cursor travels to “Save to palette” (0.70 s), then clicks | 63 / 6 / 1 |
| 5:13.99 | 7849 | ⚙ local | saved Timeline lane v2 · 2 uses updated · bindings kept | 64 / 6 / 1 |
| 5:13.99 | 7849 | 👁 screen | switches to the Renovation job canvas | 64 / 6 / 1 |
| 5:13.99 | 7849 | 👁 screen | back on the canvas (still the right-hand area): both timelines show rounder bars and “v2” | 64 / 6 / 1 |
| 5:16.79 | 7919 | 🖱 click | cursor travels to the button atom in the palette (0.70 s), then clicks | 64 / 6 / 1 |
| 5:17.77 | 7944 | 🖱 click | cursor travels to beside the bookings (0.56 s), then clicks | 64 / 6 / 1 |
| 5:18.61 | 7965 | ⚙ local | button “Notify crew” · no declared effect → downstream hole | 65 / 6 / 1 |
| 5:18.61 | 7965 | 👁 screen | a “Notify crew” button appears with a dashed “→ ? what does this do” chip | 65 / 6 / 1 |

**State at the end of chapter 14:** counters local 65 · jev 6 · large 1.

## 15 · Reload. Turn AI off. It still works.  (5:20.85 – 5:51.04 · frames 8021–8775)

> **Caption:** Everything established is stored and native. With AI off, drags, rules, the dial and critical() still run. A new decision that would need jev becomes a hole, never a guess.

### Underneath

**Reload.** Reload restores everything from storage:
- 6 elements;
- 1 user component;
- 1 checked function.

**AI off.**
- The AI switch disconnects jev and the large model.
- Dragging Floors’ end writes `Tasks#t7.duration = 2`, and `critical()` re-runs natively.

**A decision that would need jev.**
- Dropping People with AI off: Table and List tie at 1.55, so the margin is 0.
- Per spec §2.4, AI off with a margin below 0.15 gives **none**, so a hole appears. AI off with a margin of 0.15 or more would have placed the top candidate marked *unconfirmed*.
- Nothing is guessed.

### Beat by beat

| Time | Frame | Kind | What happens | L / J / G |
|---|---|---|---|---|
| 5:23.51 | 8087 | 🖱 click | cursor travels to the reload button (0.70 s), then clicks | 65 / 6 / 1 |
| 5:25.61 | 8140 | ⚙ local | reload · restored 6 elements, 1 user component, 1 function | 66 / 6 / 1 |
| 5:25.61 | 8140 | 🖱 click | cursor travels to the AI switch (0.70 s), then clicks | 66 / 6 / 1 |
| 5:26.59 | 8164 | ⚙ local | AI off · jev and large model disconnected | 67 / 6 / 1 |
| 5:26.59 | 8164 | 👁 screen | the canvas pans back to the first area | 67 / 6 / 1 |
| 5:27.85 | 8196 | 🖱 move | cursor → the right end of the Floors bar | 67 / 6 / 1 |
| 5:28.48 | 8211 | 🖱 press + drag | press on the Floors end handle and drag left one day | 67 / 6 / 1 |
| 5:29.88 | 8246 | 🖱 release | release | 67 / 6 / 1 |
| 5:29.88 | 8246 | ✎ data write | Tasks#t7.duration = 2 d (AI off) | 68 / 6 / 1 |
| 5:29.88 | 8246 | ⚙ local | critical() re-ran natively · AI off | 69 / 6 / 1 |
| 5:31.56 | 8288 | 👁 screen | the canvas pans right to the second area | 69 / 6 / 1 |
| 5:32.82 | 8320 | 🖱 move | cursor → the People collection in the palette | 69 / 6 / 1 |
| 5:33.40 | 8335 | 🖱 press + drag | press on the People collection in the palette and drag “People · 3” to the space under the button | 69 / 6 / 1 |
| 5:34.66 | 8366 | 🖱 release | release over the space under the button | 69 / 6 / 1 |
| 5:34.94 | 8373 | ▤ decision panel | drag · People → canvas → candidates: Table 1.55 · List 1.55 | 69 / 6 / 1 |
| 5:35.22 | 8380 | ⚙ local | AI off · no clear winner → hole | 70 / 6 / 1 |
| 5:35.22 | 8380 | 👁 screen | a hole appears: “? People — AI off · Table and List tie” | 70 / 6 / 1 |
| 5:38.86 | 8471 | ■ end card | end card with the final counts | 70 / 6 / 1 |

**State at the end of chapter 15:** counters local 70 · jev 6 · large 1.

## End card (5:38.86 – 5:51.04)

A dark card reading **“Most of it never touches a model.”** It has three tiles, with the counters at that moment:
- **70 local:** schema, roles, forms, records, drags, mappings, handles, rules, writes, undo, versions, reload;
- **6 jev decisions:** each a pick among candidates the engine built, plus blanks;
- **1 large-model call:** one genuinely new rule, checked, then native.

The footer says the video uses the same data, scores and rules as the prototype and the spec, and that the spec wins.

## Every decision in the video

| # | When | Request | Candidates (score) | Handler | Result |
|---|---|---|---|---|---|
| 1 | 1:58.55 | drag · Tasks → canvas | Board · group ← status 1.30 ✓ · Table 1.15 · List 1.15 · Map 0.00 (not installed) | jev | drop Tasks → Board · 180 ms · 14 tok |
| 2 | 2:27.84 | drop · status → bar.width | share where status = Done 0.81 ✓ · … = Doing 0.42 · … = To do 0.30 | jev | bar.width ← share(status = Done) · 120 ms · 6 tok |
| 3 | 2:34.49 | prompt · form to edit the selected task | Form · edit · ← board.selection 0.92 ✓ · Form · create new Task 0.61 · Table row editor 0.44 | jev | Form ← board.selection · save → update Task · 210 ms · 24 tok |
| 4 | 2:47.53 | prompt · tasks over time, one row per person | none: no installed component is temporal | local | no candidates → hole (no model call) |
| 5 | 3:40.04 | note · red if it would delay the finish | template: filter on a field 0.12 · template: count(…) ≤ n 0.08 · escalate: new function needed 0.94 ✓ | jev | note → escalate · 140 ms · 9 tok |
| 6 | 3:57.71 | retry hole · Tasks over time | Timeline lane v1 · 1 blank 1.60 ✓ | jev | hole → Timeline lane · row = assignee · 150 ms · 11 tok |
| 7 | 4:44.00 | drag · Bookings → canvas | Timeline lane v1 · 2 blanks 1.43 ✓ · Board · group ← room 1.35 · Table 1.18 · List 1.18 | jev | Bookings → Timeline lane · 2 blanks filled · 150 ms · 12 tok |
| 8 | 5:00.27 | drag · Freezer → canvas | Dial · value, max, limit, target 1.60 ✓ | local | Freezer → Dial (single candidate, local) |
| 9 | 5:34.94 | drag · People → canvas | Table 1.55 · List 1.55 | local | AI off · no clear winner → hole |

## Every data write in the video

| When | Write |
|---|---|
| 0:39.19 | create People#p1 { name: “Ana” } |
| 0:40.85 | create People#p2 { name: “Sam” } |
| 0:42.51 | create People#p3 { name: “Lee” } |
| 1:31.21 | create Tasks#t1 { title: “Demo walls”, status: Done, assignee: Ana, start: Oct 1, duration: 2 d } |
| 1:38.64 | create Tasks#t2 { title: “Order fixtures”, status: Done, assignee: Lee, start: Oct 1, duration: 2 d } |
| 1:41.00 | create Tasks#t3 { title: “Electrical”, status: Doing, assignee: Sam, start: Oct 3, duration: 3 d, depends_on: [Demo walls] } |
| 1:43.33 | create Tasks#t4 { title: “Plumbing”, status: Doing, assignee: Lee, start: Oct 3, duration: 3 d, depends_on: [Demo walls] } |
| 1:45.80 | create Tasks#t5 { title: “Drywall”, status: To do, assignee: Ana, start: Oct 6, duration: 3 d, depends_on: [Electrical, Plumbing] } |
| 1:47.97 | create Tasks#t6 { title: “Paint”, status: To do, assignee: Sam, start: Oct 9, duration: 2 d, depends_on: [Drywall] } |
| 1:50.27 | create Tasks#t7 { title: “Floors”, status: To do, assignee: Lee, start: Oct 11, duration: 3 d, depends_on: [Paint] } |
| 1:52.36 | create Tasks#t8 { title: “Final clean”, status: To do, assignee: Ana, start: Oct 14, duration: 1 d, depends_on: [Floors] } |
| 2:08.33 | Tasks#t3.status = Done (board drag) |
| 2:39.13 | Tasks#t5.status = Doing (form save) |
| 4:05.17 | Tasks#t4.duration = 4 d (end handle) |
| 4:31.16 | create Bookings#b1 { who: “Electrician”, room: Kitchen, from: Oct 3, to: Oct 6 } |
| 4:34.29 | create Bookings#b2 { who: “Plumber”, room: Pantry, from: Oct 3, to: Oct 5 } |
| 4:37.41 | create Bookings#b3 { who: “Painter”, room: Dining, from: Oct 9, to: Oct 11 } |
| 4:40.48 | create Bookings#b4 { who: “Tiler”, room: Kitchen, from: Oct 10, to: Oct 12 } |
| 4:49.43 | Bookings#b3.from = Oct 10, .to = Oct 12 (adapter inverse: move shifts both) |
| 5:07.83 | Freezer#z1.target = 8.5 °C (dial target handle) |
| 5:29.88 | Tasks#t7.duration = 2 d (AI off) |

## Final state

**Namespace · data**
- `People`: 3 records, Person{name: Text·title}.
- `Tasks`: 8 records, Task{title: Text·title, status: Enum(To do, Doing, Done)·group, assignee: Ref(People)·ref, start: Date·start, duration: Duration·duration, depends_on: Many(Tasks)}.
  - Changed during the video: t3 status Done, then undone back to Doing; t5 status → Doing; t4 duration → 4 d; t7 duration → 2 d.
- `Bookings`: 4 records, Booking{who·title, room: Enum(Kitchen, Pantry, Dining)·group, from: Date·start, to: Date·end}. Changed during the video: b3 from/to → Oct 10/Oct 12.
- `Freezer`: stream, 1 record. label, value, max and limit are read-only; target is writable (changed to 8.5 °C).

**Registry**
- Board, Table, List, Form and Dial are prepared and installed. Map is known but not installed.
- **Timeline lane v2** is yours:
  - consumes `Many<{start, duration, row, title?, fill?}>`;
  - produces moved, resized, selection;
  - handles end → duration and body → start;
  - rule no_overlap(row, interval);
  - derived fill ← critical ? red : status;
  - radius 10.

**Functions:** `critical(task, all) → Bool`, checked and native.

**Namespace · screen:** heading, subtitle, bar, board, form, schedule (Timeline lane ← Tasks), room bookings (Timeline lane ← Bookings), dial (← Freezer), and two holes: the “Notify crew” effect and People with AI off.

## Invariants the build must keep (each one is visible somewhere above)

1. Creating a collection, choosing types and inferring roles never calls a model.
1. A record form is derived from the type, one control per field type, with no model involved.
1. Every write happens on release (or Save), is one undoable step, and is logged as local.
1. Dropping data enumerates candidates **structurally**. jev is called only when a blank exists or the top two are within 0.25.
1. A single candidate with no blanks is decided locally (Freezer → Dial). An empty candidate list is a hole, never a forced fallback.
1. A field dropped on a specific element property is an explicit target, so no decision is needed.
1. Handles exist only for writable bindings. A read-only binding shows a lock and writes nothing.
1. Rules are enforced during the drag (visible violation). A rejected release writes nothing.
1. Adapters invert: moving a from/to bar writes both from and to.
1. New logic is a pure function, checked before use, then native. It still runs with AI off.
1. A saved component is a candidate like any other. A new version updates every use and keeps the bindings.
1. A control with no declared effect is a visible downstream hole.
1. After reload with AI off, everything established works. A decision that needs jev becomes a hole, or an unconfirmed top pick if the margin is at least 0.15.

## What is illustrative

- **Exact, from the prototype's `enumerate()`:** the scores for the Tasks, Tasks-temporal, Bookings, Freezer and People decisions.
- **Illustrative:** the ranking scores for the bar's blank, the edit-form prompt and the note's templates. Those are spec §2.6 operation templates the prototype doesn't implement yet.
- **Representative values, not measurements:** latencies (jev 120–210 ms, large model 1.8 s) and token counts.
- **Fake clock:** the video runs on one. The ×4 and ×2 badges mark sped-up stretches, and nothing different happens underneath during them.