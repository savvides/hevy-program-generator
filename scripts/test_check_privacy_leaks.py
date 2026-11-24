#!/usr/bin/env python3
"""Unit tests for check_privacy_leaks.py gatekeeper."""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_privacy_leaks as cpl  # noqa: E402


class TestCheckPrivacyLeaks(unittest.TestCase):

    def test_allowed_file_paths(self):
        self.assertEqual(cpl.check_file_path(".env.example"), [])
        self.assertEqual(cpl.check_file_path("data/workouts/.gitkeep"), [])
        self.assertEqual(cpl.check_file_path("programs/starter_full_body_2x.py"), [])
        self.assertEqual(cpl.check_file_path("scripts/fetch_workouts.py"), [])

    def test_forbidden_workout_files(self):
        errs = cpl.check_file_path("data/workouts/my_session.json")
        self.assertTrue(any("Personal workout session data" in e for e in errs))

        errs_sub = cpl.check_file_path("data/workouts/sub/test.csv")
        self.assertTrue(any("Personal workout session data" in e for e in errs_sub))

    def test_forbidden_env_files(self):
        errs_env = cpl.check_file_path(".env")
        self.assertTrue(any("Environment secret file" in e for e in errs_env))

        errs_local = cpl.check_file_path(".env.local")
        self.assertTrue(any("Environment secret file" in e for e in errs_local))

    def test_forbidden_custom_program(self):
        errs_prog = cpl.check_file_path("programs/program.py")
        self.assertTrue(any("User private program definition" in e for e in errs_prog))

    def test_benign_placeholder_allowed(self):
        # Placeholders in documentation or example files must not trigger false positives
        line = 'HEVY_API_KEY = "your_hevy_api_key_here"'
        match = cpl.API_KEY_REGEX.search(line)
        self.assertIsNotNone(match)
        key_val = match.group(1).lower()
        self.assertTrue(any(ph in key_val for ph in cpl.BENIGN_KEY_PLACEHOLDERS))

        consensus_line = 'CONSENSUS_API_KEY = "your_consensus_api_key_here"'
        c_match = cpl.API_KEY_REGEX.search(consensus_line)
        self.assertIsNotNone(c_match)
        c_val = c_match.group(1).lower()
        self.assertTrue(any(ph in c_val for ph in cpl.BENIGN_KEY_PLACEHOLDERS))

    def test_consensus_cache_default_file_is_clean(self):
        errs = cpl.check_consensus_cache()
        self.assertEqual(errs, [])

    def test_consensus_cache_catches_api_key(self):
        fake_key = "cs_live_" + "98765432101234567890"
        content = f'{{"CONSENSUS_API_KEY": "{fake_key}"}}'
        errs = cpl.check_consensus_cache(content=content)
        self.assertTrue(any("Possible secret API key detected" in e for e in errs))

    def test_consensus_cache_catches_json_secret_token(self):
        fake_token = "sec_live_" + "98765432101234567890"
        content = f'{{"api_key": "{fake_token}"}}'
        errs = cpl.check_consensus_cache(content=content)
        self.assertTrue(any("Possible secret or auth token detected" in e for e in errs))

    def test_consensus_cache_catches_bearer_token(self):
        fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        content = f'{{"header": "Bearer {fake_jwt}"}}'
        errs = cpl.check_consensus_cache(content=content)
        self.assertTrue(any("Possible Bearer token detected" in e for e in errs))

    def test_consensus_cache_catches_email(self):
        content = '{"contact": "researcher@sports-science.org"}'
        errs = cpl.check_consensus_cache(content=content)
        self.assertTrue(any("Personal identifier (email:" in e for e in errs))

    def test_consensus_cache_benign_placeholder_allowed(self):
        content = '{"CONSENSUS_API_KEY": "your_consensus_api_key_here"}'
        errs = cpl.check_consensus_cache(content=content)
        self.assertEqual(errs, [])

    def test_check_file_content_delegates_for_consensus_cache(self):
        # Only the consensus-cache check flags emails, so a reported email proves delegation.
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "data" / "consensus_cache.json"
            cache.parent.mkdir(parents=True)
            cache.write_text('{"contact": "researcher@sports-science.org"}\n', encoding="utf-8")
            with mock.patch.object(cpl, "REPO_ROOT", Path(tmp)):
                errs = cpl.check_file_content("data/consensus_cache.json")
        self.assertTrue(any("Personal identifier (email:" in e for e in errs))

    def test_nested_and_mixed_case_forbidden_paths(self):
        self.assertTrue(cpl.check_file_path("config/.env"))
        self.assertTrue(cpl.check_file_path(".ENV"))
        self.assertTrue(cpl.check_file_path("data/Workouts/x.json"))
        self.assertTrue(cpl.check_file_path("Programs/Program.py"))
        self.assertEqual(cpl.check_file_path("config/.env.example"), [])
        # The .env.example exemption must not exempt other rules.
        self.assertTrue(cpl.check_file_path("data/workouts/.env.example"))

    def test_archived_review_and_cache_allow_exact_public_permissions_contact(self):
        content = "For permissions, please e-mail: journals.permissions@oup.com."
        path = "data/consensus_cache.json"
        self.assertEqual(cpl.check_consensus_cache(file_path=path, content=content), [])

    def test_public_contact_exception_does_not_hide_private_emails(self):
        path = "data/consensus_cache.json"
        content = "For permissions, please e-mail: journals.permissions@oup.com. Contact private@example.org."
        errors = cpl.check_consensus_cache(file_path=path, content=content)
        self.assertEqual(len(errors), 1)
        self.assertIn("private@example.org", errors[0])

    def test_public_contact_requires_research_path_and_original_permissions_context(self):
        content = "For permissions, please e-mail: journals.permissions@oup.com."
        self.assertTrue(cpl.check_consensus_cache(file_path="data/unrelated.json", content=content))
        self.assertTrue(cpl.check_consensus_cache(content="Contact journals.permissions@oup.com."))


FAKE_KEY = "00000000-0000-0000-0000-000000000000"
CLEAN_TEXT = "".join(f"line {i}: nothing secret here\n" for i in range(10))


class TestScannerAgainstGitRepo(unittest.TestCase):
    """Run main() end to end against a throwaway git repository."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        # Drop GIT_* vars (set inside git hooks) so neither git nor the scanner hits the real repo.
        env_patch = mock.patch.dict(os.environ)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for name in [n for n in os.environ if n.startswith("GIT_")]:
            del os.environ[name]
        root_patch = mock.patch.object(cpl, "REPO_ROOT", self.repo)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.git("init", "-q")
        # Pin config that the defects depend on, so a user's global config cannot hide them.
        for key, value in [("user.name", "Test"), ("user.email", "test@example.invalid"),
                           ("commit.gpgsign", "false"), ("core.quotepath", "true"),
                           ("diff.renames", "true")]:
            self.git("config", key, value)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.repo, check=True,
                              capture_output=True, encoding="utf-8").stdout

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self) -> None:
        self.git("commit", "-q", "--no-verify", "-m", "base")

    def scan(self, *argv: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return cpl.main(list(argv))

    def test_staged_key_is_reported(self):
        self.write("notes.md", f'HEVY_API_KEY = "{FAKE_KEY}"\n')
        self.git("add", "notes.md")
        self.assertEqual(self.scan(), 1)

    def test_clean_staged_file_passes(self):
        self.write("notes.md", CLEAN_TEXT)
        self.git("add", "notes.md")
        self.assertEqual(self.scan(), 0)

    def test_staged_rename_with_key_is_reported(self):
        self.write("old.md", CLEAN_TEXT)
        self.git("add", "old.md")
        self.commit()
        self.git("mv", "old.md", "new.md")
        self.write("new.md", CLEAN_TEXT + f'HEVY_API_KEY = "{FAKE_KEY}"\n')
        self.git("add", "new.md")
        self.assertTrue(self.git("diff", "--cached", "--name-status", "-M").startswith("R"))
        self.assertEqual(self.scan(), 1)

    def test_staged_rename_to_env_is_reported(self):
        self.write("settings.txt", CLEAN_TEXT)
        self.git("add", "settings.txt")
        self.commit()
        self.git("mv", "settings.txt", ".env")
        self.assertTrue(self.git("diff", "--cached", "--name-status", "-M").startswith("R"))
        self.assertEqual(self.scan(), 1)

    def test_staged_key_is_reported_after_disk_copy_is_cleaned(self):
        self.write("notes.md", f'HEVY_API_KEY = "{FAKE_KEY}"\n')
        self.git("add", "notes.md")
        self.write("notes.md", CLEAN_TEXT)
        self.assertEqual(self.scan(), 1)

    def test_staged_key_is_reported_after_disk_copy_is_deleted(self):
        self.write("notes.md", f'HEVY_API_KEY = "{FAKE_KEY}"\n')
        self.git("add", "notes.md")
        (self.repo / "notes.md").unlink()
        self.assertEqual(self.scan(), 1)

    def test_non_ascii_filename_is_scanned(self):
        self.write("notes-é.md", f'HEVY_API_KEY = "{FAKE_KEY}"\n')
        self.git("add", "notes-é.md")
        self.assertEqual(self.scan(), 1)
        self.assertEqual(self.scan("--all"), 1)

    def test_nested_env_file_is_reported(self):
        self.write("config/.env", "HEVY_API_KEY=placeholder\n")
        self.git("add", "-f", "config/.env")
        self.assertEqual(self.scan(), 1)

    def test_nested_env_example_is_allowed(self):
        self.write("config/.env.example", "HEVY_API_KEY=your_hevy_api_key_here\n")
        self.git("add", "-f", "config/.env.example")
        self.assertEqual(self.scan(), 0)

    def test_assignment_forms_are_reported(self):
        forms = [
            f'os.environ["HEVY_API_KEY"] = "{FAKE_KEY}"',
            f'api_key: str = "{FAKE_KEY}"',
            f'apiKey = "{FAKE_KEY}"',
            f"HEVY_KEY={FAKE_KEY}",
        ]
        for line in forms:
            with self.subTest(line=line):
                self.write("settings.py", line + "\n")
                self.git("add", "settings.py")
                self.assertEqual(self.scan(), 1)
                self.git("rm", "-q", "--cached", "settings.py")

    def test_svg_is_scanned(self):
        self.write("logo.svg", f'<svg data-api-key="{FAKE_KEY}"/>\n')
        self.git("add", "logo.svg")
        self.assertEqual(self.scan(), 1)

    def test_git_failure_is_scanner_error(self):
        os.environ["GIT_DIR"] = str(self.repo / "missing")
        self.assertEqual(self.scan(), 2)
        self.assertEqual(self.scan("--all"), 2)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read mode-000 files")
    def test_unreadable_file_is_scanner_error(self):
        self.write("notes.md", CLEAN_TEXT)
        self.git("add", "notes.md")
        path = self.repo / "notes.md"
        path.chmod(0)
        self.addCleanup(path.chmod, 0o644)
        self.assertEqual(self.scan("--all"), 2)


if __name__ == "__main__":
    unittest.main()
