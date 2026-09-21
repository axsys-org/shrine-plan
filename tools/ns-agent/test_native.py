"""End-to-end invariants exercised against compiled Foil and real Shrine."""
import os
import json
from pathlib import Path
import tempfile
import unittest

from runtime import Native, validate
from runner import Session, MAX_OPERATIONS


class ValidationTests(unittest.TestCase):
    def test_goal_validation(self):
        condition = {"path": "/release/tests", "care": "x", "note": "Tests pass", "met": False}
        op = {"op": "make", "path": "/goals/release", "fields": {
            "/app/goal": {"conditions": {"tests": condition}}}}
        wire = validate(op)
        self.assertEqual(wire["fields"]["/app/goal"]["conditions"]["tests"]["path"], ["release", "tests"])
        self.assertEqual(condition["path"], "/release/tests")
        for goal in [{"conditions": {}}, {"conditions": {"tests": condition}, "fulfilled": True},
                     {"conditions": {"tests": {**condition, "met": "true"}}},
                     {"conditions": {"tests": {**condition, "path": "/goals/release"}}},
                     {"conditions": {"tests": {**condition, "path": "/goals", "care": "z"}}}]:
            with self.subTest(goal=goal), self.assertRaises(ValueError):
                validate({**op, "fields": {"/app/goal": goal}})
        with self.assertRaises(ValueError):
            validate({**op, "fields": {**op["fields"], "/sys/crew": {}}})
    def test_dependency_validation(self):
        good = {"op": "make", "path": "/notes/count", "fields": {
            "note": "Check count", "/sys/crew": {"users": {"path": "/users", "care": "z"}}}}
        self.assertEqual(validate(good)["fields"]["/sys/crew"]["users"]["path"], ["users"])
        self.assertEqual(good["fields"]["/sys/crew"]["users"]["path"], "/users")
        for dep in [{"path": "/agent", "care": "z"}, {"path": "/", "care": "z"},
                    {"path": "/users", "care": "bad"}, {"path": "/users"}]:
            with self.assertRaises(ValueError):
                validate({**good, "fields": {"/sys/crew": {"users": dep}}})
    def test_paths_and_values(self):
        for path in ["users/a", "/users//a", "/users/../a", "/users/a/", "/users/\x00"]:
            with self.assertRaises(ValueError):
                validate({"op": "make", "path": path, "fields": {}})
        for path in ["/", "/agent/events/a", "/boot", "/log/a", "/h", "/io/a"]:
            with self.assertRaises(ValueError):
                validate({"op": "cull", "path": path})
        with self.assertRaises(ValueError):
            validate({"op": "poke", "path": "/users/a"})
        with self.assertRaises(ValueError):
            validate({"op": "make", "path": "/users/a", "fields": {"n": float('nan')}})


@unittest.skipUnless(os.environ.get("WISP"), "Set WISP and AGENT_RUNTIME to run native integration tests")
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = Native(os.environ["WISP"], Path(os.environ["AGENT_RUNTIME"]),
                        Path(os.environ["AGENT_SEED"]) if os.environ.get("AGENT_SEED") else None)

    @classmethod
    def tearDownClass(cls):
        cls.ns.close()

    def setUp(self):
        self.ns.reset()

    def op(self, op, path, fields=None):
        data = {"op": op, "path": path}
        if fields is not None:
            data["fields"] = fields
        return self.ns.op(data)

    def test_roundtrip_and_case(self):
        fields = {"name": 'Iañ "test"\nline', "active": True, "empty": "", "null": None,
                  "negative": -5, "large": 2**80, "nested": {"xs": [1, False, "a"]}}
        made = self.op("make", "/users/ian", fields)
        self.assertTrue(made["ok"])
        self.assertEqual(made["ack"], "/users/ian")
        self.assertEqual(made["changes"][0]["after"], fields)
        read = self.op("read", "/users/ian")["records"][0]
        self.assertEqual(read["fields"], fields)
        repeated = self.op("make", "/users/ian", fields)
        self.assertTrue(repeated["ok"])
        self.assertEqual(repeated["changes"], [])
        self.assertEqual(self.op("read", "/users/ian")["records"][0]["case"], read["case"])

    def test_merge_replace_and_recursive_cull(self):
        self.op("make", "/users/ian", {"name": "Ian", "active": True})
        self.op("make", "/users/ian/note", {"text": "keep child"})
        patch = self.op("poke", "/users/ian", {"active": False})
        self.assertEqual(patch["changes"][0]["after"], {"name": "Ian", "active": False})
        self.op("make", "/users/ian", {"name": "New"})
        rows = self.op("read", "/users/ian")["records"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["fields"], {"name": "New"})
        culled = self.op("cull", "/users/ian")
        self.assertEqual({c["path"] for c in culled["changes"]}, {"/users/ian", "/users/ian/note"})
        self.assertTrue(all(c["after"] is None for c in culled["changes"]))
        self.assertEqual(self.op("read", "/users")["records"], [])

    def test_failed_poke_does_not_commit(self):
        result = self.op("poke", "/missing", {"n": 1})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "poke_missing")
        self.assertEqual(result["changes"], [])
        self.assertEqual(self.op("read", "/")["records"], [])

    def watch(self, path="/notes/count", care="z", target="/users"):
        if care in {"y", "z"}:
            records = self.op("read", target)["records"]
            if not any(r["path"] == target for r in records):
                self.op("make", target, {})
        return self.op("make", path, {"note": "Check the user count", "/sys/crew": {
            "users": {"path": target, "care": care}}})

    def test_native_dependency_note_roundtrip_and_real_hear(self):
        self.watch()
        note = self.op("read", "/notes/count")["records"][0]["fields"]
        self.assertEqual(note["/sys/crew"], {"users": {"path": "/users", "care": "z"}})
        r = self.op("make", "/users/ian", {"name": "Ian"})
        self.assertEqual(r["rounds"], 2)  # driving transaction then native hear
        self.assertEqual(r["outbound_count"], 1)
        self.assertEqual(len(r["notifications"]), 1)
        n = r["notifications"][0]
        self.assertEqual(n["watcher"], "/notes/count")
        self.assertEqual(n["note"], "Check the user count")
        self.assertEqual(n["dependencies"]["users"]["records"], [{"path": "/users", "fields": {}}, {"path": "/users/ian", "fields": {"name": "Ian"}}])
        self.assertEqual({c["path"] for c in r["changes"]}, {"/users/ian"})
        self.assertEqual(self.op("read", "/notes/count")["records"][0]["case"], 1)

    def test_noop_unrelated_and_unwiring_are_quiet(self):
        self.watch()
        self.op("make", "/users/ian", {"name": "Ian"})
        for r in [self.op("make", "/users/ian", {"name": "Ian"}), self.op("make", "/other", {})]:
            self.assertEqual(r["notifications"], [])
        self.op("poke", "/notes/count", {"/sys/crew": {}})
        self.assertEqual(self.op("make", "/users/josh", {})["notifications"], [])

    def goal_conditions(self, tests=False, approval=False):
        return {
            "tests": {"path": "/release/tests", "care": "x", "note": "All tests pass", "met": tests},
            "approval": {"path": "/release/approval", "care": "x", "note": "Release approved", "met": approval}}

    def goal_state(self):
        return self.op("read", "/goals/release")["records"][0]["fields"]["/app/goal"]

    def assess_goal(self, tests, approval):
        return self.op("poke", "/goals/release", {
            "/app/goal": {"conditions": self.goal_conditions(tests, approval)}})

    def test_goal_native_completion_and_selective_reopening(self):
        for path in ["/release/tests", "/release/approval"]:
            self.op("make", path, {"ok": True})
        self.op("make", "/goals/release", {"note": "Keep release safe", "/app/goal": {
            "conditions": self.goal_conditions()}})
        self.assertFalse(self.goal_state()["fulfilled"])
        self.assess_goal(True, False)
        self.assertFalse(self.goal_state()["fulfilled"])
        r = self.assess_goal(True, True)
        self.assertEqual(r["notifications"], [])
        self.assertTrue(self.goal_state()["fulfilled"])
        self.assertEqual(self.goal_state()["conditions"], self.goal_conditions(True, True))
        # No-op and unrelated changes cannot invalidate assessed conditions.
        self.assertEqual(self.op("poke", "/release/tests", {"ok": True})["notifications"], [])
        self.assertEqual(self.op("make", "/unrelated", {})["notifications"], [])
        self.assertTrue(self.goal_state()["fulfilled"])
        # Reopening happens in Shrine, with no host/model call.
        r = self.op("poke", "/release/tests", {"ok": False})
        self.assertFalse(self.goal_state()["fulfilled"])
        self.assertEqual(self.goal_state()["conditions"], self.goal_conditions(False, True))
        self.assertEqual(len(r["notifications"]), 1)
        notice = r["notifications"][0]
        self.assertEqual(notice["watcher_record"]["/app/goal"], self.goal_state())
        self.assertEqual(notice["dependencies"]["tests"]["records"][0]["fields"], {"ok": False})
        self.assertEqual({c["path"] for c in r["changes"]}, {"/release/tests", "/goals/release"})
        self.op("poke", "/release/tests", {"ok": True})
        self.assertFalse(self.goal_state()["fulfilled"])  # evidence must be reassessed
        self.assess_goal(True, True)
        self.assertTrue(self.goal_state()["fulfilled"])
        self.op("cull", "/release/approval")
        self.assertEqual(self.goal_state()["conditions"], self.goal_conditions(True, False))
        self.assertFalse(self.goal_state()["fulfilled"])

    def test_goal_managed_wiring_note_edits_and_removal(self):
        self.op("make", "/goals/release", {"note": "Old note", "/app/goal": {
            "conditions": self.goal_conditions(True, True)}})
        self.assertTrue(self.goal_state()["fulfilled"])  # native init computes too
        self.assertFalse(self.op("poke", "/goals/release", {"/sys/crew": {}})["ok"])
        self.op("poke", "/goals/release", {"note": "Reconsider release"})
        r = self.op("make", "/release/tests", {"ok": True})
        self.assertEqual(r["notifications"][0]["note"], "Reconsider release")
        self.assertFalse(self.goal_state()["conditions"]["tests"]["met"])
        # Rewiring replaces native dependencies as well as the condition map.
        new = {"quality": {"path": "/quality", "care": "x", "note": "Quality passes", "met": False}}
        self.op("poke", "/goals/release", {"/app/goal": {"conditions": new}})
        self.assertEqual(self.op("cull", "/release/tests")["notifications"], [])
        self.assertEqual(len(self.op("make", "/quality", {})["notifications"]), 1)
        self.op("cull", "/goals/release")
        self.assertEqual(self.op("poke", "/quality", {"ok": True})["notifications"], [])

    def test_goal_subtree_condition_uses_native_care(self):
        self.op("make", "/users", {})
        conditions = {"users": {"path": "/users", "care": "z", "note": "Users ready", "met": True}}
        self.op("make", "/goals/release", {"/app/goal": {"conditions": conditions}})
        self.assertTrue(self.goal_state()["fulfilled"])
        r = self.op("make", "/users/ian", {})
        self.assertEqual(len(r["notifications"]), 1)
        self.assertFalse(self.goal_state()["fulfilled"])

    def test_care_and_deletion_and_note_refresh(self):
        self.op("make", "/users", {})
        self.watch("/notes/x", "x")
        self.watch("/notes/z", "z")
        r = self.op("make", "/users/ian", {})
        self.assertEqual([n["watcher"] for n in r["notifications"]], ["/notes/z"])
        self.op("poke", "/notes/z", {"note": "New reminder"})
        r = self.op("cull", "/users/ian")
        self.assertEqual(r["notifications"][0]["note"], "New reminder")
        self.assertEqual(r["notifications"][0]["dependencies"]["users"]["records"], [{"path": "/users", "fields": {}}])
        self.op("cull", "/notes/z")
        self.assertEqual(self.op("make", "/users/josh", {})["notifications"], [])

    def test_self_watch_does_not_mutate_itself_forever(self):
        r = self.watch("/notes/self", "x", "/notes/self")
        self.assertEqual(r["rounds"], 2)
        self.assertEqual(len(r["notifications"]), 1)

    def test_absent_exact_target_and_legacy_transparent_parent_replay(self):
        self.watch("/notes/exact", "x", "/absent/person")
        r = self.op("make", "/absent/person", {})
        self.assertEqual(len(r["notifications"]), 1)
        # Reproduce a command accepted by the old adapter, using real Shrine.
        old = {"op": "make", "path": "/notes/tree", "fields": {
            "note": "native semantics", "/sys/crew": {"tree": {"path": "/transparent", "care": "z"}}}}
        self.ns._execute(old, validate(old))
        self.assertEqual(self.op("make", "/transparent/child", {})["notifications"], [])
        before = self.op("read", "/")["records"]
        self.ns.restore(self.ns.current_operations)
        self.assertEqual(self.op("read", "/")["records"], before)
        with self.assertRaisesRegex(ValueError, "Make /transparent"):
            self.ns.op(old)
        self.assertEqual(len(self.op("make", "/transparent", {})["notifications"]), 1)

    def test_subtree_note_preflight_rejects_without_mutation_then_native_wake(self):
        for care in ["y", "z"]:
            with self.subTest(care=care):
                self.ns.reset()
                fields = {"note": "Count users", "/sys/crew": {"users": {"path": "/users", "care": care}}}
                with self.assertRaisesRegex(ValueError, "not an existing record"):
                    self.op("make", "/summary", fields)
                self.op("make", "/users/ian", {"name": "Ian"})
                before = self.op("read", "/")["records"]
                count = len(self.ns.current_operations)
                with self.assertRaisesRegex(ValueError, "implicit parent.*Make /users"):
                    self.op("make", "/summary", fields)
                self.assertEqual(self.op("read", "/")["records"], before)
                self.assertEqual(len(self.ns.current_operations), count)
                self.op("make", "/users", {})
                self.assertTrue(self.op("make", "/summary", fields)["ok"])
                result = self.op("make", "/users/josh", {"name": "Josh"})
                self.assertEqual([n["watcher"] for n in result["notifications"]], ["/summary"])
                self.assertEqual(self.op("read", "/users/ian")["records"], before)
                before = self.op("read", "/summary")["records"]
                with self.assertRaisesRegex(ValueError, "Make /other"):
                    self.ns.op({"op": "poke", "path": "/summary", "fields": {
                        "note": "Must not change", "/sys/crew": {"other": {"path": "/other", "care": care}}}}, internal=True)
                self.assertEqual(self.op("read", "/summary")["records"], before)
                self.assertEqual(len(self.op("cull", "/users/josh")["notifications"]), 1)

    def test_goal_tool_checks_subtree_roots_on_creation_and_rewire(self):
        class NoCalls:
            budget, spent = 1, 0

        for care in ["y", "z"]:
            with self.subTest(care=care), tempfile.TemporaryDirectory() as folder:
                session = Session(self.ns, NoCalls(), Path(folder))
                self.op("make", "/users/ian", {})
                self.ns.op({"op": "make", "path": "/goals/release", "fields": {
                    "note": "Users ready", "/app/goal": {"conditions": {}}}}, internal=True)
                args = {"path": "/goals/release", "note": "Users ready", "why": "Track users",
                        "conditions": {"users": {"path": "/users", "care": care, "note": "Users ready", "met": True}}}
                with self.assertRaisesRegex(ValueError, "Make /users"):
                    session.goal_operation(args)
                self.assertEqual(self.goal_state()["conditions"], {})
                self.op("make", "/users", {})
                self.assertTrue(session.goal_operation(args)["ok"])
                before = self.op("read", "/goals/release")["records"]
                with self.assertRaisesRegex(ValueError, "Make /missing"):
                    session.goal_operation({**args, "conditions": {"missing": {
                        "path": "/missing", "care": care, "note": "Missing", "met": False}}})
                self.assertEqual(self.op("read", "/goals/release")["records"], before)
                result = self.op("make", "/users/josh", {})
                self.assertEqual([n["watcher"] for n in result["notifications"]], ["/goals/release"])
                self.assertFalse(self.goal_state()["fulfilled"])

    def test_same_make_can_assert_its_own_note_watch_root(self):
        for care in ["y", "z"]:
            with self.subTest(care=care):
                self.ns.reset()
                result = self.op("make", "/notes/self", {"note": "Observe this tree", "/sys/crew": {
                    "self": {"path": "/notes/self", "care": care}}})
                self.assertTrue(result["ok"])
                self.assertEqual(len(self.op("make", "/notes/self/child", {})["notifications"]), 1)

    def test_resume_preserves_records_conversation_and_cost_without_model_call(self):
        class NoCalls:
            budget, spent = 1, .02

            def complete(self, _):
                raise AssertionError("Replay must not call the model")

        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.ns, NoCalls(), Path(folder))
            session.turn(external={"op": "make", "path": "/users/ian", "fields": {"name": "Ian"}})
            before = session.snapshot()
            resumed = Session(self.ns, NoCalls(), Path(folder), resume=True)
            after = resumed.snapshot()
            for field in ["session_id", "records", "messages", "events", "total_spent"]:
                self.assertEqual(before[field], after[field])

    def test_chat_switch_replays_independent_namespaces_and_legacy_history(self):
        class NoCalls:
            budget, spent = 1, .02

            def complete(self, _):
                raise AssertionError("Chat switching must not call the model")

        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.ns, NoCalls(), Path(folder))
            first = session.session_id
            session.turn(external={"op": "make", "path": "/source", "fields": {"value": 1}})
            session.turn(external={"op": "make", "path": "/goals/source", "fields": {
                "/app/goal": {"conditions": {"source": {"path": "/source", "care": "x", "note": "Value is one", "met": True}}}}})
            saved = session.snapshot()
            session.reset()
            second = session.session_id
            self.assertNotEqual(first, second)
            self.assertEqual(session.records, [])
            session.turn(external={"op": "make", "path": "/source", "fields": {"value": 2}})
            second_saved = session.snapshot()
            session.client.spent = .12
            # Simulate an older saved chat, whose tape only exists in the original journal.
            (Path(folder) / f"{first}.operations.jsonl").unlink()
            session.switch_chat(first)
            self.assertEqual(session.records, saved["records"])
            self.assertEqual(session.events, saved["events"])
            self.assertEqual(session.messages, saved["messages"])
            self.assertEqual(session.client.spent, .12)
            self.assertEqual(len(session.chats()), 2)
            session.switch_chat(second)
            self.assertEqual(session.records, second_saved["records"])
            resumed = Session(self.ns, NoCalls(), Path(folder), resume=True)
            self.assertEqual(resumed.session_id, second)
            self.assertEqual(resumed.records, second_saved["records"])
            self.assertEqual(resumed.client.spent, .12)
            resumed.switch_chat(first)
            r = self.op("poke", "/source", {"value": 9})
            self.assertEqual(r["notifications"][0]["watcher"], "/goals/source")
            self.assertFalse(r["notifications"][0]["watcher_record"]["/app/goal"]["fulfilled"])

    def test_failed_chat_restore_rolls_back_current_native_state(self):
        class NoCalls:
            budget, spent = 1, 0

        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.ns, NoCalls(), Path(folder))
            first = session.session_id
            session.turn(external={"op": "make", "path": "/one", "fields": {}})
            session.reset()
            session.turn(external={"op": "make", "path": "/two", "fields": {}})
            second = session.snapshot()
            (Path(folder) / f"{first}.operations.jsonl").write_text("")
            with self.assertRaisesRegex(RuntimeError, "differs"):
                session.switch_chat(first)
            self.assertEqual(session.session_id, second["session_id"])
            self.assertEqual(self.op("read", "/")["records"], second["records"])
            self.assertEqual(session.events, second["events"])

    def test_ui_goal_is_committed_before_any_model_decision(self):
        class Unavailable:
            budget, spent = 1, 0

            def complete(self, _):
                raise RuntimeError("Model unavailable")

        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.ns, Unavailable(), Path(folder))
            with self.assertRaisesRegex(RuntimeError, "Model unavailable"):
                session.turn(goal_description="Keep release ready")
            records = self.op("read", "/goals")["records"]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["fields"]["note"], "Keep release ready")
            self.assertEqual(records[0]["fields"]["/app/goal"], {"conditions": {}, "fulfilled": False})
            self.assertEqual(session.events[0]["data"]["intent"], "goal")
            self.assertEqual(session.events[2]["data"]["ack"], records[0]["path"])

    def test_goal_tool_uses_native_operations_and_preserves_other_fields(self):
        class NoCalls:
            budget, spent = 1, 0

        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.ns, NoCalls(), Path(folder))
            args = {"path": "/goals/release", "note": "Keep release ready", "conditions": self.goal_conditions(), "why": "Track readiness"}
            with self.assertRaisesRegex(ValueError, "New goals require"):
                session.goal_operation(args)
            self.ns.op({"op": "make", "path": args["path"], "fields": {
                "note": args["note"], "/app/goal": {"conditions": {}}}}, internal=True)
            self.assertTrue(session.goal_operation(args)["ok"])
            self.op("poke", "/goals/release", {"owner": "Ian"})
            result = session.goal_operation({**args, "conditions": self.goal_conditions(True, True)})
            self.assertTrue(result["ok"])
            fields = self.op("read", "/goals/release")["records"][0]["fields"]
            self.assertTrue(fields["/app/goal"]["fulfilled"])
            self.assertEqual(fields["owner"], "Ian")
            self.op("make", "/ordinary", {"keep": True})
            with self.assertRaisesRegex(ValueError, "ordinary record"):
                session.goal_operation({**args, "path": "/ordinary"})
            self.assertEqual(self.op("read", "/ordinary")["records"][0]["fields"], {"keep": True})

    def test_observation_is_native_but_not_application_data(self):
        self.ns.op({"op": "make", "path": "/agent/events/e1", "fields": {"kind": "user"}}, internal=True)
        self.assertEqual(self.op("read", "/")["records"], [])
        self.assertEqual(self.op("read", "/agent/events")["records"][0]["fields"], {"kind": "user"})
        log = self.op("read", "/log")["records"]
        self.assertGreater(len(log), 0)
        self.assertIn("See what follows.", self.ns.page())

    def run_batch(self, operations):
        class ScriptedClient:
            budget, spent, n = 1, 0, 0

            def complete(self, _messages):
                self.n += 1
                calls = [{"id": str(i), "type": "function", "function": {
                    "name": "ns", "arguments": json.dumps(op)}}
                    for i, op in enumerate(operations)]
                message = {"role": "assistant", "content": "", "tool_calls": calls} if self.n == 1 else {
                    "role": "assistant", "content": "Stopping this protocol test."}
                return message, {"usage": {}, "cost": 0, "latency_ms": 0, "request_bytes": 0}

        with tempfile.TemporaryDirectory() as folder:
            session = Session(self.ns, ScriptedClient(), Path(folder))
            session.turn("Protocol test")
            return session.snapshot()

    def test_batch_executes_in_order_with_individual_feedback_and_causal_join(self):
        s = self.run_batch([
            {"op": "make", "path": "/a", "fields": {"value": 1}},
            {"op": "poke", "path": "/a", "fields": {"value": 2}},
            {"op": "read", "path": "/a"}])
        operations = [e for e in s["events"] if e["kind"] == "operation"]
        results = [e for e in s["events"] if e["kind"] == "result"]
        self.assertEqual(len({e["parent"] for e in operations}), 1)
        self.assertEqual([e["parent"] for e in results], [e["id"] for e in operations])
        self.assertTrue(all(e["data"]["ok"] for e in results))
        self.assertEqual(results[1]["data"]["changes"][0]["before"], {"value": 1})
        self.assertEqual(results[2]["data"]["records"][0]["fields"], {"value": 2})
        self.assertEqual(s["events"][-1]["parent"], [e["id"] for e in results])
        record = self.op("read", s["events"][-1]["ref"])["records"][0]
        self.assertEqual(record["fields"]["from"], [e["ref"] for e in results])
        replies = [m for m in s["messages"] if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in replies], ["0", "1", "2"])
        self.assertEqual([json.loads(m["content"])["observation_ref"] for m in replies],
                         [e["ref"] for e in results])

    def test_batch_failure_preserves_success_and_skips_remaining_calls(self):
        for bad in [{"op": "poke", "path": "/missing", "fields": {}},
                    {"op": "make", "path": "/notes/bad", "fields": {
                        "/sys/crew": {"missing": {"path": "/missing", "care": "z"}}}},
                    {"op": "cull", "path": "/agent"}]:
            with self.subTest(bad=bad):
                s = self.run_batch([
                    {"op": "make", "path": "/kept", "fields": {}}, bad,
                    {"op": "cull", "path": "/kept"}])
                results = [e["data"] for e in s["events"] if e["kind"] == "result"]
                self.assertTrue(results[0]["ok"])
                self.assertFalse(results[1]["ok"])
                self.assertTrue(results[2]["skipped"])
                self.assertFalse(results[2]["executed"])
                self.assertEqual([r["path"] for r in s["records"]], ["/kept"])
                self.assertEqual(len([m for m in s["messages"] if m["role"] == "tool"]), 3)
                self.ns.restore(self.ns.current_operations)
                self.assertEqual(self.op("read", "/")["records"], s["records"])

    def test_batch_keeps_native_notifications_at_their_originating_result(self):
        s = self.run_batch([
            {"op": "make", "path": "/notes/source", "fields": {
                "note": "Check progress", "/sys/crew": {"source": {"path": "/source", "care": "x"}}}},
            {"op": "make", "path": "/source", "fields": {"value": 1}},
            {"op": "poke", "path": "/source", "fields": {"value": 2}}])
        results = [e for e in s["events"] if e["kind"] == "result"]
        notices = [e for e in s["events"] if e["kind"] == "dependency"]
        self.assertEqual([e["parent"] for e in notices], [e["id"] for e in results[1:]])
        self.assertEqual([e["data"]["dependencies"]["source"]["records"][0]["fields"]["value"]
                          for e in notices], [1, 2])
        self.assertEqual(s["events"][-1]["parent"], [results[0]["id"], *[e["id"] for e in notices]])
        self.assertEqual(next(r for r in s["records"] if r["path"] == "/source")["fields"], {"value": 2})

    def test_oversized_batch_does_not_execute_any_calls(self):
        s = self.run_batch([{"op": "make", "path": f"/item-{i}", "fields": {}}
                            for i in range(MAX_OPERATIONS + 1)])
        self.assertEqual(s["records"], [])
        replies = [json.loads(m["content"]) for m in s["messages"] if m["role"] == "tool"]
        self.assertEqual(len(replies), MAX_OPERATIONS + 1)
        self.assertTrue(all(r["skipped"] and not r["executed"] for r in replies))


if __name__ == "__main__":
    unittest.main(verbosity=2)
