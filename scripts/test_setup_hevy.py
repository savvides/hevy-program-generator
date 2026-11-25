#!/usr/bin/env python3
"""Unit tests for Hevy API key setup, verification, and actionable error messages."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_routines as br
import fetch_workouts as fw
import setup_hevy as sh

SAMPLE_TOKEN = "demo-hevy-token-0123456789"


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class PlaceholderDetectionTests(unittest.TestCase):
    def test_placeholder_and_missing_values_detected(self):
        for val in (
            None,
            "",
            "   ",
            "your-key-here",
            "your_hevy_api_key_here",
            "PLACEHOLDER",
            "<your-api-key>",
        ):
            with self.subTest(val=val):
                self.assertTrue(sh.is_placeholder_key(val))

    def test_real_looking_token_not_treated_as_placeholder(self):
        self.assertFalse(sh.is_placeholder_key(SAMPLE_TOKEN))

    def test_missing_key_message_distinguishes_missing_and_placeholder(self):
        missing_msg = sh.missing_key_message(None)
        placeholder_msg = sh.missing_key_message("your-key-here")
        self.assertIn("is not set", missing_msg)
        self.assertIn("template placeholder", placeholder_msg)
        for msg in (missing_msg, placeholder_msg):
            self.assertIn(sh.DEVELOPER_SETTINGS_URL, msg)
            self.assertIn("setup_hevy.py", msg)
            self.assertIn("Hevy Pro", msg)


class WriteEnvKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_creates_env_from_example_preserving_other_entries(self):
        example = self.root / ".env.example"
        example.write_text(
            "# comment\nHEVY_API_KEY=your-key-here\nCONSENSUS_API_KEY=keep-me\n",
            encoding="utf-8",
        )
        env_path = self.root / ".env"

        sh.write_env_key(env_path, SAMPLE_TOKEN, example)

        text = env_path.read_text(encoding="utf-8")
        self.assertIn(f"HEVY_API_KEY={SAMPLE_TOKEN}", text)
        self.assertIn("CONSENSUS_API_KEY=keep-me", text)
        self.assertNotIn("your-key-here", text)
        if os.name == "posix":
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_updates_existing_env_in_place_and_preserves_other_keys(self):
        env_path = self.root / ".env"
        env_path.write_text(
            "HEVY_PROGRAM=programs/upper_lower_4x.py\n"
            "HEVY_API_KEY=old-key\n"
            "CONSENSUS_API_KEY=consensus-val\n",
            encoding="utf-8",
        )

        sh.write_env_key(env_path, SAMPLE_TOKEN)

        lines = env_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines,
            [
                "HEVY_PROGRAM=programs/upper_lower_4x.py",
                f"HEVY_API_KEY={SAMPLE_TOKEN}",
                "CONSENSUS_API_KEY=consensus-val",
            ],
        )

    def test_appends_when_existing_env_has_no_hevy_key_line(self):
        env_path = self.root / ".env"
        env_path.write_text("CONSENSUS_API_KEY=consensus-val\n", encoding="utf-8")

        sh.write_env_key(env_path, SAMPLE_TOKEN)

        lines = env_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines,
            ["CONSENSUS_API_KEY=consensus-val", f"HEVY_API_KEY={SAMPLE_TOKEN}"],
        )


class VerifyApiKeyTests(unittest.TestCase):
    def test_verify_success_reports_workout_count(self):
        with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse({"workout_count": 42})):
            ok, msg = sh.verify_api_key(SAMPLE_TOKEN)
        self.assertTrue(ok)
        self.assertIn("42", msg)

    def test_verify_401_and_403_include_setup_guidance(self):
        for code in (401, 403):
            err = urllib.error.HTTPError("https://api.hevyapp.com/v1/workouts/count", code, "Auth", None, None)
            with self.subTest(code=code), patch("urllib.request.urlopen", side_effect=err):
                ok, msg = sh.verify_api_key(SAMPLE_TOKEN)
            self.assertFalse(ok)
            self.assertIn(str(code), msg)
            self.assertIn(sh.DEVELOPER_SETTINGS_URL, msg)
            self.assertIn("Hevy Pro", msg)

    def test_verify_network_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            ok, msg = sh.verify_api_key(SAMPLE_TOKEN)
        self.assertFalse(ok)
        self.assertIn("Could not reach Hevy API", msg)


class SetupCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env_path = Path(self.tmp.name) / ".env"

    def _run_cli(self, *args: str, env_override: dict[str, str] | None = None):
        out = io.StringIO()
        err = io.StringIO()
        env = {k: v for k, v in os.environ.items() if k != "HEVY_API_KEY"}
        if env_override:
            env.update(env_override)
        with patch.dict(os.environ, env, clear=True), \
             contextlib.redirect_stdout(out), \
             contextlib.redirect_stderr(err):
            rc = sh.main(["--env-file", str(self.env_path), *args])
        return rc, out.getvalue(), err.getvalue()

    def test_check_missing_key(self):
        rc, _, err = self._run_cli("--check")
        self.assertEqual(rc, 1)
        self.assertIn(sh.DEVELOPER_SETTINGS_URL, err)
        self.assertIn("setup_hevy.py", err)

    def test_check_placeholder_key(self):
        self.env_path.write_text("HEVY_API_KEY=your-key-here\n", encoding="utf-8")
        rc, _, err = self._run_cli("--check")
        self.assertEqual(rc, 1)
        self.assertIn("placeholder", err)

    def test_check_valid_key_succeeds_without_printing_key(self):
        self.env_path.write_text(f"HEVY_API_KEY={SAMPLE_TOKEN}\n", encoding="utf-8")
        with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse({"workout_count": 7})):
            rc, out, err = self._run_cli("--check")
        self.assertEqual(rc, 0)
        self.assertIn("7", out)
        self.assertEqual(err, "")
        self.assertNotIn(SAMPLE_TOKEN, out)

    def test_interactive_valid_key_verifies_and_saves(self):
        with patch("getpass.getpass", return_value=SAMPLE_TOKEN), \
             patch("urllib.request.urlopen", return_value=_FakeHTTPResponse({"workout_count": 3})):
            rc, out, err = self._run_cli()
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertNotIn(SAMPLE_TOKEN, out)
        self.assertIn(f"HEVY_API_KEY={SAMPLE_TOKEN}", self.env_path.read_text(encoding="utf-8"))

    def test_interactive_invalid_key_does_not_write_env(self):
        rejected = urllib.error.HTTPError("https://api.hevyapp.com/v1/workouts/count", 401, "Unauthorized", None, None)
        with patch("getpass.getpass", return_value=SAMPLE_TOKEN), \
             patch("urllib.request.urlopen", side_effect=rejected):
            rc, _, err = self._run_cli()
        self.assertEqual(rc, 1)
        self.assertIn("401", err)
        self.assertFalse(self.env_path.exists())


class ScriptAuthErrorIntegrationTests(unittest.TestCase):
    def test_fetch_workouts_rejects_missing_and_placeholder_keys_with_guidance(self):
        for key in (None, "your-key-here"):
            env = {k: v for k, v in os.environ.items() if k != "HEVY_API_KEY"}
            if key is not None:
                env["HEVY_API_KEY"] = key
            err = io.StringIO()
            with self.subTest(key=key), \
                 patch.object(fw, "load_dotenv"), \
                 patch.dict(os.environ, env, clear=True), \
                 contextlib.redirect_stderr(err):
                rc = fw.main([])
            self.assertEqual(rc, 1)
            self.assertIn(sh.DEVELOPER_SETTINGS_URL, err.getvalue())
            self.assertIn("setup_hevy.py", err.getvalue())

    def test_build_routines_rejects_placeholder_on_sync_and_warns_on_dry_run(self):
        env = {k: v for k, v in os.environ.items() if k != "HEVY_API_KEY"}
        env["HEVY_API_KEY"] = "your-key-here"

        err = io.StringIO()
        with patch.object(br, "load_dotenv"), \
             patch.dict(os.environ, env, clear=True), \
             contextlib.redirect_stderr(err):
            rc = br.main(["--skip-qa"])
        self.assertEqual(rc, 1)
        self.assertIn(sh.DEVELOPER_SETTINGS_URL, err.getvalue())
        self.assertIn("setup_hevy.py", err.getvalue())

        out = io.StringIO()
        with patch.object(br, "load_dotenv"), \
             patch.dict(os.environ, env, clear=True), \
             patch("urllib.request.urlopen", side_effect=AssertionError("dry-run must not send placeholder key")), \
             contextlib.redirect_stdout(out):
            rc = br.main(["--skip-qa", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("placeholder", out.getvalue())


if __name__ == "__main__":
    unittest.main()
