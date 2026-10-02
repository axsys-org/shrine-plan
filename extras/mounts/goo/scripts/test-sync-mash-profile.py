#!/usr/bin/env python3
"""Exercise the cross-repository profile integrity boundary without Mash present."""
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("sync-mash-profile.py")
SPEC = importlib.util.spec_from_file_location("sync_mash_profile", SCRIPT)
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class ProfileIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="goo-profile-test-")
        self.addCleanup(self.temp.cleanup)
        self.bundle = pathlib.Path(self.temp.name) / "profile"
        shutil.copytree(SYNC.VENDOR, self.bundle)

    def test_committed_bundle_and_generated_native_profile_agree(self):
        profile = SYNC.verify_bundle(self.bundle)
        self.assertEqual(SYNC.generate(profile), (SYNC.ROOT / "profile.foil").read_text())

    def test_changed_font_bytes_are_rejected(self):
        profile = json.loads((self.bundle / "profile.json").read_text())
        font = self.bundle / next(iter(profile["fonts"].values()))["file"]
        font.write_bytes(font.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "failed verification"):
            SYNC.verify_bundle(self.bundle)

    def test_resealed_asset_hash_cannot_hide_a_changed_profile_revision(self):
        profile_path = self.bundle / "profile.json"
        profile = json.loads(profile_path.read_text())
        profile["textStyles"]["default"]["pixels"] += 1
        profile_path.write_text(json.dumps(profile))
        manifest_path = self.bundle / "assets.json"
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest["files"]:
            if entry["path"] == "profile.json":
                entry["sha256"] = SYNC.digest(profile_path.read_bytes())
                entry["bytes"] = profile_path.stat().st_size
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "revision does not match"):
            SYNC.verify_bundle(self.bundle)

    def test_unlisted_assets_are_rejected(self):
        (self.bundle / "unexpected.css").write_text("body {font-family:serif}")
        with self.assertRaisesRegex(ValueError, "inventory does not match"):
            SYNC.verify_bundle(self.bundle)

    def test_canonical_numbers_match_javascript_revision_protocol(self):
        self.assertEqual(
            '{"a":0.00001,"b":[14,0,-0.65,1.48],"z":1e-7}',
            SYNC.canonical({"z":1e-7,"b":[14.0,-0.0,-0.65,1.48],"a":1e-5}),
        )


if __name__ == "__main__":
    unittest.main()
