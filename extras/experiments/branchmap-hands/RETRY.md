# Retry in a fresh chat

Select Astra and the reasoning setting you want to compare. Start a new chat with this prompt after installing the adjacent `skills/shrine-branchmap-retry` skill directory in `~/.codex/skills/`. Replace the two paths with your source repository and a new destination.

```text
Use $shrine-branchmap-retry to reconstruct the Branchmap experiment from scratch.

Source repository: /path/to/shrine-plan
Fresh destination: /path/to/branchmap-retry-01

Use the skill's default combined harness baseline and frozen inputs. Build both
milestones, with as much domain logic as possible inside Shrine, and make the
application usable through goo-egui. Record the actual model/settings and
validation evidence. Give your own assessment before consulting earlier runs.
Keep the result local; do not launch another agent or a paid model hand.
```

The preparation script exports the harness before either Branchmap implementation was added. It copies the paper and data, not the previous controller, native mount, quote graph, or feedback. Record prior exposure honestly: this controls files, not a model's inherited context. For a harness comparison, repeat in another fresh chat with the same model/settings and inputs, changing only `--revision` to another application-free harness commit.
