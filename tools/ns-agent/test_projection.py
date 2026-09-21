"""Model-input fidelity and size, independently of native execution."""
import copy
import json
import unittest

from context import field_changes, model_context


def record(path, fields, case=1):
    return {"path": path, "fields": fields, "case": case}


def result_message(result, number=1):
    return {"role": "tool", "tool_call_id": str(number), "content": json.dumps({
        **result, "observation_ref": f"/agent/events/e{number:05d}"})}


def packet(messages):
    return json.loads(messages[-1]["content"].split("\n", 1)[1])


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.note = "Keep the derived value consistent with the source; never change the source to satisfy it."
        self.watcher = {"note": self.note, "/sys/crew": {"source": {"path": "/source", "care": "x"}}}

    def notice(self, value, watcher="/derived"):
        return {"watcher": watcher, "note": self.note, "watcher_record": self.watcher,
                "changed": [{"path": "/source", "care": "x"}], "dependencies": {
                    "source": {"path": "/source", "care": "x", "records": [record("/source", {"n": value})]}}}

    def test_repeated_snapshots_become_one_current_copy_without_changing_transcript(self):
        calls = [{"id": str(i), "type": "function", "function": {
            "name": "ns", "arguments": json.dumps({"op": "poke", "path": "/source", "fields": {"n": i}})}}
                 for i in range(1, 13)]
        messages = [{"role": "user", "content": "Keep these exact requirements. Ask about the unresolved exception."},
                    {"role": "assistant", "content": "I will make the changes.", "tool_calls": calls,
                     "reasoning_details": [{"type": "reasoning.encrypted", "data": "signed-provider-state"}]}]
        for i in range(1, 13):
            messages.append(result_message({"ok": True, "ack": "/source", "changes": [
                {"path": "/source", "case": i, "before": {"n": i - 1}, "after": {"n": i}}],
                "notifications": [self.notice(i)]}, i))
        original = copy.deepcopy(messages)
        records = [record("/source", {"n": 12}, 12), record("/derived", self.watcher),
                   record("/unseen", {"secret": "should not be in this view"})]
        projected = model_context(messages, records)
        self.assertEqual(messages, original)
        self.assertEqual(projected[:2], messages[:2])
        self.assertEqual([m["tool_call_id"] for m in projected if m["role"] == "tool"], [str(i) for i in range(1, 13)])
        self.assertEqual(json.dumps(projected).count(self.note), 1)
        current = packet(projected)
        self.assertEqual(current["records"]["/source"], {"fields": {"n": 12}, "case": 12})
        self.assertNotIn("/unseen", current["records"])
        self.assertEqual(len(current["activations"]), 1)
        self.assertEqual(len(current["activations"][0]["causes"]), 12)
        self.assertLess(len(json.dumps(projected)), len(json.dumps(messages)) * .85)
        first = json.loads(projected[2]["content"])
        self.assertEqual(first["changes"][0]["fields"], [{"field": ["n"], "before": 0, "after": 1}])

    def test_native_current_state_wins_over_earlier_callback_in_batch(self):
        messages = [result_message({"ok": True, "notifications": [self.notice(1)]})]
        current = packet(model_context(messages, [record("/source", {"n": 2}, 2), record("/derived", self.watcher)]))
        self.assertEqual(current["records"]["/source"]["fields"], {"n": 2})
        self.assertEqual(current["activations"][0]["views_observed_at"], "/agent/events/e00001")

    def test_missing_empty_null_and_slot_names_are_distinct(self):
        before = {"/app/goal": {"met": True}, "literal_null": 3, "removed": None, "number": True}
        after = {"/app/goal": {"met": False}, "literal_null": None, "number": 1, "new_null": None}
        diffs = field_changes(before, after)
        self.assertIn({"field": ["removed"], "before": None, "removed": True}, diffs)
        self.assertIn({"field": ["literal_null"], "before": 3, "after": None}, diffs)
        self.assertIn({"field": ["new_null"], "added": None}, diffs)
        self.assertIn({"field": ["number"], "before": True, "after": 1}, diffs)
        self.assertIn({"field": ["/app/goal", "met"], "before": True, "after": False}, diffs)
        messages = [result_message({"ok": True, "records": [record("/empty", {}), record("/gone", {"n": 1})]})]
        current = packet(model_context(messages, [record("/empty", {})]))["records"]
        self.assertEqual(current["/empty"]["fields"], {})
        self.assertEqual(current["/gone"], {"absent": True})

    def test_diagnostics_noops_and_deleted_fields_survive(self):
        outcomes = [{"ok": True, "ack": "/source", "changes": []},
                    {"ok": False, "executed": False, "skipped": True, "error": "earlier call failed", "changes": []},
                    {"ok": True, "cascade_error": "fuel exhausted", "changes": [{"path": "/source",
                     "case": 2, "before": {"n": 3}, "after": None}]}]
        projected = model_context([result_message(r, i) for i, r in enumerate(outcomes)], [])
        self.assertEqual(json.loads(projected[0]["content"])["changes"], [])
        self.assertFalse(json.loads(projected[1]["content"])["executed"])
        self.assertTrue(json.loads(projected[1]["content"])["skipped"])
        self.assertEqual(json.loads(projected[2]["content"])["cascade_error"], "fuel exhausted")
        self.assertEqual(json.loads(projected[2]["content"])["changes"][0]["previous_fields"], {"n": 3})

    def test_interrupted_activation_and_siblings_survive_until_final_response(self):
        messages = [result_message({"ok": True, "notifications": [self.notice(1), self.notice(1, "/sibling")]}),
                    {"role": "user", "content": "Continue after the interrupted response"},
                    result_message({"ok": True, "notifications": [self.notice(2)]}, 2)]
        records = [record("/derived", self.watcher), record("/sibling", self.watcher)]
        current = packet(model_context(messages, records))
        self.assertEqual({a["watcher"] for a in current["activations"]}, {"/derived", "/sibling"})
        self.assertEqual(len(current["activations"][0]["causes"]), 2)
        messages.append({"role": "assistant", "content": "Finished checking both."})
        self.assertEqual(packet(model_context(messages, records))["activations"], [])

    def test_deleted_watcher_keeps_its_fired_note_and_internal_read_is_not_absence(self):
        messages = [result_message({"ok": True, "notifications": [self.notice(1)], "records": [
            record("/agent/events/e00001", {"kind": "user", "data": {"text": "original"}})]})]
        current = packet(model_context(messages, []))
        self.assertEqual(current["records"]["/derived"], {"absent": True})
        self.assertEqual(current["activations"][0]["earlier_notes"][0]["note"], self.note)
        self.assertIn("fields_at_observation", current["records"]["/agent/events/e00001"])

    def test_legacy_host_messages_require_grounded_native_events(self):
        op = {"op": "poke", "path": "/source", "fields": {"n": 1}}
        result = {"ok": True, "notifications": [self.notice(1)]}
        text = "External namespace operation: " + json.dumps(op) + "\nActual result: " + json.dumps(result)
        messages = [{"role": "user", "content": text}]
        self.assertEqual(model_context(messages, []), messages)
        events = [{"id": "e00001", "ref": "/agent/events/e00001", "kind": "external", "data": op},
                  {"id": "e00002", "ref": "/agent/events/e00002", "kind": "result", "parent": "e00001", "data": result}]
        projected = model_context(messages, [record("/derived", self.watcher)], events)
        self.assertIn("Native outcome:", projected[0]["content"])
        self.assertNotIn("watcher_record", projected[0]["content"])
        self.assertEqual(packet(projected)["activations"][0]["causes"][0]["observation_ref"], "/agent/events/e00002")

    def test_host_metadata_never_reaches_provider(self):
        result = {"ok": True, "records": [record("/source", {"n": 1})]}
        events = [{"id": "e00001", "ref": "/agent/events/e00001", "kind": "result", "data": result}]
        message = {"role": "user", "content": "archival payload", "_context_text": "Preserve user intent",
                   "_context_observations": [events[0]["ref"]]}
        projected = model_context([message], [record("/source", {"n": 1})], events)
        self.assertEqual(set(projected[0]), {"role", "content"})
        self.assertTrue(projected[0]["content"].startswith("Preserve user intent"))


if __name__ == "__main__":
    unittest.main()
