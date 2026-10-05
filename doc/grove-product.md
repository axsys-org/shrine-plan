# Grove: what we are building

*A description of the real product the demo videos point to. Build this for real: no scripted clock, no fake numbers.*

---

## In one paragraph

Grove lets anyone build real software by sketching it. You block out a screen in rough boxes and words, and within a moment it becomes a real, good-looking interface: a floor plan you can draw on, a 3D view you can spin, charts, tables, documents, image editors. Each part says plainly what it still needs ("where does this come from?", "where does this go?"). You answer by connecting things you already have, dropping in a file, or sketching the missing piece. Every answer becomes durable working software that you can reuse. The AI does the interpreting quietly and never gets between your hand and the thing you're touching. Turn it off and everything you built keeps working.

---

## 1. How it should feel

- **Like snapping blocks, not drawing with a mouse.** Boxes snap to each other and to a grid, labels sit inside them, connectors stick to the edges they come from. A rough sketch looks rough on purpose, but it is never messy.
- **Like the software is already there.** You don't wait for a generated page. Each region you sketch turns into a real component in place, one region at a time, while you keep working on the next.
- **Like direct manipulation, always.** Drag a wall and the 3D view, the chart and the total move with your hand, every frame. Nothing you touch ever waits on the network or the AI.
- **Calm and honest.** Missing pieces are shown, not hidden or guessed silently. Proposals say exactly what will change before anything does. There is no chatbot to persuade and no spinner pretending to be progress.
- **Rich, never dumb.** If you sketch something visual, you get the visual thing: a plan, a scene, a chart, a document. Not a stack of text fields.
- **Yours.** Everything you make lands in your namespace, inspectable and reusable, and keeps working without the model.

---

## 2. The screen

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Tabs: Renovation · Tasks · Photo · +              network · AI on/off    │
├───────────────┬──────────────────────────────────────────┬───────────────┤
│ NAMESPACE     │ Trail: Renovation › Total › Quote         │ ACTIVITY      │
│ search        │                                          │ local · native│
│ ingest file   │   your working surface                   │ check · model │
│ material      │   (sketch here; real UI appears here)    │ what ran,     │
│ native ops    │                                          │ how long      │
│ constructions │                                          │ (hideable)    │
└───────────────┴──────────────────────────────────────────┴───────────────┘
```

- **Namespace (left):** everything that exists in your world. Files you dropped in, collections (Rooms, People, Tasks), native operations (extrude, area, sum), and constructions you built (Renovation screen, Person picker, paint cost). Things appear here the moment they exist. You can drag any of them into your work.
- **Trail (top):** where you are when you've gone deeper to build a missing piece: `Task form › Assignee › Person picker`. Click back up at any time; nothing you did down there is lost.
- **Surface (centre):** a normal scrolling page where you sketch and where the real UI lives. Tabs keep separate surfaces and remember exactly where you were.
- **Activity (right, hideable):** a quiet log of what actually happened: local, native, check, adapter, model, elsewhere. It shows real timings and how many times the model was actually called.

**Colour always means the same thing:**

| Colour | Means |
|---|---|
| Pencil blue | your sketch |
| Dashed amber | something is missing, always with its type and its question |
| Violet | proposed by the AI, not yet real |
| Green | native, checked, working |
| Ink | your action |

---

## 3. Sketching

You sketch with a small set of pieces that snap:

- **Box:** drag it out; it snaps to the grid and lines up with its neighbours. Boxes inside boxes are containers.
- **Label:** just type while a box is selected. `plan`, `3D`, `cost by room`, `total`.
- **Field and button shorthand:** typing `Title [____]` makes a field, `[ Create ]` makes a button, `( People )` makes a list, `task | person | status` makes a table.
- **Stamps:** quick symbols for the common visual things: chart axes, a cube for 3D, an image, a map, a timeline, a document.
- **Connectors:** pull from a region's edge to say "this feeds that". They stay attached when things move.
- **Notes:** a few words pinned to a region or a line, like "+ paint, 2 coats" or "glow where bright". Notes are how you describe behavior.

Freehand pen strokes are allowed but tidy themselves into boxes, lines and arrows when you lift the pen. Anything that doesn't tidy becomes a note.

Sketching itself is instant and never involves the AI.

---

## 4. From sketch to real UI

When a region you sketched has been still for a moment (about 700 ms), it turns into real UI in place:

- `plan` with a grid becomes a **floor-plan editor** with real units.
- A box with a cube and `3D` becomes a **3D viewport** you can orbit.
- Axes and bars with `cost by room` become a **chart**.
- `total $` becomes a **big number with its breakdown**.
- `Title [____]` and `[ Create ]` become a **form with a real button**.
- A heading, a few lines and a signature line become a **document**.

Only the region you just changed refreshes. Anything you're typing in is never replaced under you. The first version appears immediately as a sensible placeholder and sharpens within a second or two.

**Every region tells you what it is.** A small chip on each one says what it needs or makes:

- Floor plan: `draws → ? Room`
- 3D preview: `← needs Scene`
- Cost by room: `← needs cost per room`
- Total: `Σ derived · produces Quote →`

---

## 5. The two questions

Every missing piece is one of two questions, and the product always asks them in the same way:

- **"Where does this come from?"** An input with nothing feeding it yet: the 3D view needs a Scene, the picker needs People.
- **"Where does this go?"** An output with nowhere to land yet: Create task makes a Task, but nothing holds Tasks.

Click the amber chip and you get the answers in a fixed order:

1. **Something that already exists** in your world.
2. **Something you built before** that fits.
3. **A built-in conversion** that bridges the gap. For example, *extrude* turns room outlines into a 3D scene.
4. **✎ Draw it from here:** go one level deeper and sketch the missing piece. When it's done, you come back up and the hole is filled.

You can always just **type into a field** or **draw on a canvas**. Human input is a perfectly good answer; not everything needs a source.

---

## 6. Connecting things

You connect by dragging: a file onto a need, a collection onto a chart, a picker you built onto a new field. While you drag, compatible targets light up immediately.

When you drop, you watch the system work it out in a visible sequence:

1. **What you dropped and what it needs to be.**
2. **Does it already fit?** If so, it's connected, and the remaining steps say "not needed".
3. **Is there a built-in conversion?**
4. **If not, the AI is asked only the smallest remaining question** (for example, "which material goes with which room, and how is it priced?").
5. **If the meaning is genuinely ambiguous, you're asked right there.** "Price per m² applies to floor area or wall area?" One click.

**Proposals.** When something new has to exist (a Room type, a Materials list, a Quotes collection), you get one violet card that says exactly:
- what will be created,
- where it will live and who owns it,
- what it may write (new things only, or changes to existing ones),
- where it looked before concluding nothing like it existed,
- and a preview of the result.

One **Accept**. Undo is one click.

**Nothing happens by accident.** Finishing a picker doesn't choose anyone for you. Creating a "Create quote" button doesn't create quotes. Things run when you use them.

---

## 7. Living with what you built

This is where it stops feeling like a generator and starts feeling like an instrument.

- **Drag anything that has a handle.** A wall, a curve point, a slider, a keyframe. Every connected view updates in the same frame: plan, 3D, chart, total.
- **One selection everywhere.** Select Living on the plan and it lights up in 3D and in the chart. Brush part of a chart and the same items highlight in every view.
- **Snapshots stay snapshots.** A Quote records what things were when it was made. Change a wall afterwards and the quote stays the same, showing "1 change since".
- **Change how it looks without changing what it means.** Turn bars into a donut, a dropdown into an autocomplete, a list into a board. The data, the connections and your selection stay put.
- **Reuse anything.** The Person picker you built for tasks drops straight into a Review form. The paint cost you added works on any room.
- **Edits are safe.** If someone else changes something unrelated while you're typing, your typing stands. If they changed the very thing you're editing, you see their version next to yours and choose. Re-sorting a list never sends your edit to the wrong row.
- **Close it and come back.** Tabs, where you were in the trail, and half-typed drafts are all there after a reload.
- **Turn the AI off.** Everything you built keeps running: forms, pickers, collections, charts, 3D, behaviors, quotes. The AI is only needed to make something new.

---

## 8. When something genuinely new is needed

Sometimes nothing existing can do what your note asks: "+ paint, 2 coats", "glow where bright", "click to advance status". Then:

1. The product first says what it found ("perimeter and height exist; paint does not").
2. The AI writes **one small behavior** (or, for a new kind of visual, one new component) with its scope written on it: what it reads, what it writes, and that it changes nothing else.
3. It's **checked before it can run**, and you see the checks pass.
4. It's added to your namespace and works from then on like anything built in, including with the AI off.

If it fails, you're told plainly, the previous working version stays, and the spot stays a visible hole.

The second time you need the same kind of thing, it's already there.

---

## 9. What it can make

### The visual vocabulary
| Kind | Examples |
|---|---|
| Spatial editors | floor plans, seating charts, garden beds, warehouse layouts, shape canvases with real units and snapping |
| 3D | room previews, terrain from an image, product mock-ups, anything built by a conversion from your data |
| Charts | bar, stacked, line, area, donut, histogram, scatter, sparkline, with brushing that drives selection |
| Collections | tables you can edit, lists, boards, galleries / contact sheets, trees |
| Choosers | pickers, autocompletes, grouped lists, avatar grids |
| Documents | quotes, invoices, reports, letters: snapshots you can print |
| Image surfaces | exact pixel selection, adjustments, transforms, before/after |
| Time | timelines with keyframes, Gantt-style schedules, calendars |
| Pipelines | node graphs showing how data flows from source to view |
| Maps | places, routes, regions bound to your records |
| Plain parts | fields, buttons, totals, tabs, cards, when that is genuinely what's needed |

### Things you could build, each starting from a sketch
- **Renovation planner:** draw rooms, see them in 3D, price floors and paint from a supplier list, issue quotes. *(the main reference video)*
- **Task tracker:** a form, a person picker built from a people list, a task list that fills as you create, and a status that advances with a click. *(the first video)*
- **Photo pipeline:** drop photos, adjust tones with a curve, make a 3D relief, chart brightness, add a glow, animate dusk to night, swap the source photo. *(the node-canvas video)*
- **Family allowance board:** kids, chores, money and savings goals. Ticking chores pays into each child's money, which funds goals with progress bars.
- **Event seating planner:** sketch tables on a floor plan, drop in a guest CSV, drag guests to seats, and print place cards as a document.
- **Garden planner:** beds on a plan, plants from a list, a sun-hours chart by bed, and a planting timeline.
- **Small-shop inventory:** a shelf layout in 3D, stock levels as a heatmap on the layout, and reorder documents when stock is low.
- **Workout log:** sessions on a calendar, lifts in a table, progress lines, and a weekly volume chart.
- **Classroom planner:** lessons on a timeline, a student picker reused across forms, and grade distributions.
- **Field-photo survey:** photos pinned to a map, exact-pixel annotations, and a report snapshot.

Each one starts as four or five rough boxes and grows by answering "where does this come from?" and "where does this go?".

---

## 10. What it never does

- Make you talk to a chatbot to get anything done.
- Freeze your hand while the AI thinks.
- Change your data without showing you exactly what will change first.
- Pretend something works when it's still missing a piece.
- Hand you a stack of form fields when you sketched a picture.
- Hide what something means inside code you can't inspect.
- Stop working when the AI is off.

---

## 11. The deliverable: the videos, for real

The finished product must be able to do each reference video live, with real data, real timing and a real model.

**Renovation planner** (`02-renovation-planner`, the main target)
1. Sketch four regions; they become a plan editor, 3D view, chart and total, each with its need. *(0:06)*
2. Draw a room with exact live dimensions; accept the proposed Room; draw two more. *(0:23)*
3. The 3D view takes the extrude conversion with no AI call; spin it; select a room in both views. *(0:35)*
4. Drop the price list; answer the floor-or-wall question; accept; choose a floor per room. *(0:46)*
5. Note "+ paint, 2 coats"; a checked paint behavior appears and stacks onto the chart. *(1:08)*
6. Follow "where does this go?" from the total to a sketched Quote; accept; create and inspect Quote#41. *(1:18)*
7. Drag a wall: plan, 3D, chart and total move together; the quote keeps its snapshot. *(1:40)*
8. Bars become a donut with nothing lost; turn the AI off and make another quote. *(1:45)*

**Task app** (`01-canvas-reset`): sketch a form; build the Person picker from a CSV; pick and return; build the task list downstream; add the status behavior; create, inspect and edit safely across a re-sort; swap picker style; reuse it and reload; AI off; do the same on an image surface.

**Photo pipeline** (`03-node-canvas`): the visual high end, curves, 3D relief, linked brushing, a new glow, a timeline, a source swap. This is the range the product should grow into.

**It's done when**, using it live:
- sketching feels like snapping blocks,
- real, good-looking UI appears region by region within a second or two,
- dragging anything updates every connected view instantly,
- every missing piece is visible and answerable by connecting, dropping or sketching,
- every new thing is proposed clearly and accepted once,
- it all keeps working with the AI off.

---

*Companion files: `REFERENCE.md` (timestamps, the feel as checkable rules, and the failure cases the videos don't show) and `appendix-engineering.md` (one possible way to build it; optional).*