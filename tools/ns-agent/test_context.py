"""User-controlled goal creation and context reset against real Shrine state."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runner import Session
from runtime import Native


class Client:
    budget, spent = 1, 0

    def __init__(self, *replies):
        self.replies = list(replies)
        self.inputs = []

    def complete(self, messages):
        self.inputs.append(copy.deepcopy(messages))
        if not self.replies:
            raise RuntimeError("No scripted response")
        return self.replies.pop(0), {"usage": {}, "cost": 0, "latency_ms": 0, "request_bytes": 0}


def call(name, args):
    return {"role": "assistant", "content": "", "tool_calls": [{"id": "test", "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)}}]}


@unittest.skipUnless(os.environ.get("WISP"), "Set WISP and AGENT_RUNTIME for native tests")
class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = Native(os.environ["WISP"], Path(os.environ["AGENT_RUNTIME"]),
                            Path(os.environ["AGENT_SEED"]) if os.environ.get("AGENT_SEED") else None)

    @classmethod
    def tearDownClass(cls):
        cls.native.close()

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.output = Path(folder.name)
        self.session = Session(self.native, Client(), self.output)
        self.native.op({"op": "make", "path": "/source", "fields": {"ready": False}})
        self.session._refresh()

    def proposal(self, note="Keep source ready", care="x"):
        return {"summary": "Keep source readiness; omit the earlier conversation.", "goals": [{
            "path": "/goals/source", "note": note, "why": "Preserve the ongoing rule",
            "conditions": {"source": {"path": "/source", "care": care,
                                     "note": "Source must have ready true", "met": False}}}]}

    def propose(self, proposal=None):
        self.session.client = Client(call("propose_compression", proposal or self.proposal()))
        self.session.turn("Compress the conversation, keeping source readiness")
        return self.session.pending_compression["ref"]

    def test_implicit_goal_creation_is_rejected_through_both_tools(self):
        args = self.proposal()["goals"][0]
        with self.assertRaisesRegex(ValueError, "New goals require"):
            self.session.goal_operation(args)
        for op in ["make", "poke"]:
            with self.assertRaisesRegex(ValueError, "New goals require"):
                self.session.model_operation({"op": op, "path": args["path"], "fields": {
                    "note": args["note"], "/app/goal": {"conditions": args["conditions"]}}})
        self.assertEqual(self.native.op({"op": "read", "path": "/goals"})["records"], [])

    def test_new_goal_button_keeps_context_and_allows_later_assessment(self):
        self.session.messages.append({"role": "user", "content": "EARLIER-CONTEXT"})
        with self.assertRaisesRegex(RuntimeError, "No scripted response"):
            self.session.turn(goal_description="Keep source ready")
        record = self.native.op({"op": "read", "path": "/goals"})["records"][0]
        self.assertEqual(record["fields"]["/app/goal"]["conditions"], {})
        self.assertEqual(self.session.context_generation, 0)
        self.assertIn("EARLIER-CONTEXT", json.dumps(self.session.messages))
        result = self.session.goal_operation({**self.proposal()["goals"][0], "path": record["path"]})
        self.assertTrue(result["ok"])

    def test_native_cascade_uses_factored_input_and_keeps_full_native_observations(self):
        s = self.session
        self.native.op({"op": "make", "path": "/derived", "fields": {
            "ready": False, "note": "Mirror source readiness; don't change source", "/sys/crew": {
                "source": {"path": "/source", "care": "x"}}}})
        s._refresh()
        s.client = Client(call("ns", {"op": "poke", "path": "/derived", "fields": {"ready": True},
                                     "why": "Source became ready"}),
                          {"role": "assistant", "content": "Derived readiness now follows source."})
        s.turn(external={"op": "poke", "path": "/source", "fields": {"ready": True}})
        first = s.client.inputs[0]
        self.assertIn("Native outcome:", first[-2]["content"])
        self.assertNotIn("watcher_record", json.dumps(first))
        context = json.loads(first[-1]["content"].split("\n", 1)[1])
        self.assertTrue(context["records"]["/source"]["fields"]["ready"])
        self.assertEqual(context["activations"][0]["watcher"], "/derived")
        native_result = next(e for e in s.events if e["kind"] == "result")
        self.assertIn("watcher_record", native_result["data"]["notifications"][0])
        self.assertIn("watcher_record", s.messages[1]["content"])
        stored = self.native.op({"op": "read", "path": native_result["ref"]})["records"][0]
        self.assertEqual(stored["fields"]["data"], native_result["data"])
        self.assertTrue(next(r for r in s.records if r["path"] == "/derived")["fields"]["ready"])
        before = s.model_messages()
        restored = Session(self.native, Client(), self.output, resume=True)
        self.assertEqual(restored.model_messages(), before)

    def test_failed_model_turn_keeps_fired_watches_when_user_continues(self):
        s = self.session
        self.native.op({"op": "make", "path": "/note", "fields": {"note": "Check source readiness",
            "/sys/crew": {"source": {"path": "/source", "care": "x"}}}})
        with self.assertRaisesRegex(RuntimeError, "No scripted response"):
            s.turn(external={"op": "poke", "path": "/source", "fields": {"ready": True}})
        s.client = Client({"role": "assistant", "content": "Source is ready."})
        s.turn("Continue")
        context = json.loads(s.client.inputs[0][-1]["content"].split("\n", 1)[1])
        self.assertEqual(context["activations"][0]["watcher"], "/note")
        self.assertTrue(context["records"]["/source"]["fields"]["ready"])

    def test_proposal_has_no_application_effect_until_approved(self):
        s = self.session
        s.messages.append({"role": "user", "content": "UNNEEDED-OLD-DETAIL"})
        original = copy.deepcopy(s.records)
        ref = self.propose()
        self.assertEqual(s.records, original)
        self.assertEqual(s.context_generation, 0)
        self.assertIn("UNNEEDED-OLD-DETAIL", json.dumps(s.messages))
        self.assertEqual(self.native.op({"op": "read", "path": ref})["records"][0]["fields"]["kind"], "compression_proposal")
        with self.assertRaisesRegex(ValueError, "no longer current"):
            s.review_compression("/agent/events/wrong", approve=True)
        s.review_compression(ref, approve=True)
        self.assertEqual(s.context_generation, 1)
        self.assertIsNone(s.pending_compression)
        self.assertNotIn("UNNEEDED-OLD-DETAIL", json.dumps(s.messages))
        self.assertIn("Keep source ready", json.dumps(s.messages))
        self.assertNotIn(self.proposal()["summary"], json.dumps(s.messages))
        goal = self.native.op({"op": "read", "path": "/goals/source"})["records"][0]
        self.assertFalse(goal["fields"]["/app/goal"]["fulfilled"])
        self.assertEqual(self.native.op({"op": "read", "path": "/source"})["records"], original)
        archived = list((self.output / "contexts" / s.session_id).glob("*.json"))
        self.assertEqual(len(archived), 1)
        self.assertIn("UNNEEDED-OLD-DETAIL", archived[0].read_text())
        for path in ["/agent/events", "/log", "/h"]:
            with self.assertRaisesRegex(ValueError, "user audit"):
                s.model_operation({"op": "read", "path": path})
        self.assertTrue(s.model_operation({"op": "read", "path": "/goals"})["ok"])
        s.client = Client({"role": "assistant", "content": "Observed source readiness."})
        s.turn(external={"op": "poke", "path": "/source", "fields": {"ready": True}})
        model_input = json.dumps(s.client.inputs[0])
        self.assertNotIn("UNNEEDED-OLD-DETAIL", model_input)
        self.assertIn("Keep source ready", model_input)
        self.assertTrue(any(e["kind"] == "dependency" for e in s.events))

    def test_correction_replaces_approval_target_and_only_revised_goals_commit(self):
        old_ref = self.propose()
        s = self.session
        revised = self.proposal("Revised rule: ready means externally approved")
        s.client = Client(call("propose_compression", revised))
        s.turn("Correction: ready must mean externally approved")
        ref = s.pending_compression["ref"]
        self.assertNotEqual(ref, old_ref)
        with self.assertRaisesRegex(ValueError, "no longer current"):
            s.review_compression(old_ref, approve=True)
        s.review_compression(ref, approve=True)
        self.assertIn(revised["goals"][0]["note"], json.dumps(s.messages))
        self.assertEqual(next(r for r in s.records if r["path"] == "/goals/source")["fields"]["note"], revised["goals"][0]["note"])

    def test_external_change_withdraws_proposal_and_dismiss_keeps_context(self):
        ref = self.propose()
        s = self.session
        s.turn(external={"op": "poke", "path": "/source", "fields": {"ready": True}})
        self.assertIsNone(s.pending_compression)
        with self.assertRaisesRegex(ValueError, "no longer current"):
            s.review_compression(ref, approve=True)
        ref = self.propose()
        before = copy.deepcopy(s.messages)
        s.review_compression(ref, approve=False)
        self.assertEqual(s.messages[:len(before)], before)
        self.assertEqual(s.context_generation, 0)
        self.assertIsNone(s.pending_compression)
        self.assertFalse(any("/app/goal" in r["fields"] for r in s.records))

    def test_approval_rechecks_native_watch_roots_before_writing(self):
        ref = self.propose(self.proposal(care="z"))
        s = self.session
        self.native.op({"op": "cull", "path": "/source"})
        before = copy.deepcopy(s.messages)
        with self.assertRaisesRegex(ValueError, "Make /source"):
            s.review_compression(ref, approve=True)
        self.assertEqual(s.messages, before)
        self.assertEqual(s.context_generation, 0)
        self.assertEqual(self.native.op({"op": "read", "path": "/goals"})["records"], [])

    def test_partial_installation_never_resets_context(self):
        proposal = self.proposal()
        proposal["goals"].append({**copy.deepcopy(proposal["goals"][0]), "path": "/goals/second"})
        ref = self.propose(proposal)
        s = self.session
        before = copy.deepcopy(s.messages)
        native_op = self.native.op

        def fail_second(operation, **kwargs):
            if operation["op"] == "make" and operation["path"] == "/goals/second":
                return {"ok": False, "error": "Injected test failure", "changes": []}
            return native_op(operation, **kwargs)

        with patch.object(self.native, "op", side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, "context retained"):
                s.review_compression(ref, approve=True)
        self.assertEqual(s.messages[:len(before)], before)
        self.assertEqual(s.context_generation, 0)
        self.assertTrue(self.native.op({"op": "read", "path": "/goals/source"})["records"])
        self.assertEqual(self.native.op({"op": "read", "path": "/goals/second"})["records"], [])

    def test_review_and_compacted_context_survive_chat_switch_and_restart(self):
        ref = self.propose()
        s = self.session
        first = s.session_id
        s.reset()
        self.assertIsNone(s.pending_compression)
        s.switch_chat(first)
        self.assertEqual(s.pending_compression["ref"], ref)
        resumed = Session(self.native, Client(), self.output, resume=True)
        self.assertEqual(resumed.pending_compression["ref"], ref)
        resumed.review_compression(ref, approve=True)
        compacted = copy.deepcopy(resumed.messages)
        resumed.reset()
        resumed.switch_chat(first)
        self.assertEqual(resumed.messages, compacted)
        resumed = Session(self.native, Client(), self.output, resume=True)
        self.assertEqual(resumed.messages, compacted)
        self.assertEqual(resumed.context_generation, 1)
        self.assertIsNone(resumed.pending_compression)

    def test_proposal_cannot_be_batched_with_mutations(self):
        message = call("propose_compression", self.proposal())
        message["tool_calls"].extend(call("ns", {"op": "make", "path": "/unexpected", "fields": {}})["tool_calls"])
        message["tool_calls"][1]["id"] = "second"
        self.session.client = Client(message, {"role": "assistant", "content": "Will propose separately."})
        self.session.turn("Compress")
        self.assertIsNone(self.session.pending_compression)
        self.assertEqual(self.native.op({"op": "read", "path": "/unexpected"})["records"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
