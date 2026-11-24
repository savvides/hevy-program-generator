#!/usr/bin/env python3
"""Unit tests for the import-health QA gate."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import check_import_health  # noqa: E402
from check_import_health import (  # noqa: E402
    check_file,
    python_files,
    uses_argparse,
)


class TestDiscovery(unittest.TestCase):
    def test_collects_scripts_and_programs(self):
        found = python_files()
        names = {p.name for p in found}
        self.assertIn("consensus_client.py", names)
        self.assertIn("three_day_split_3x.py", names)
        self.assertGreater(len(found), 30)

    def test_every_collected_file_exists(self):
        for path in python_files():
            self.assertTrue(path.is_file(), f"{path} is not a file")


class TestArgparseDetection(unittest.TestCase):
    def test_detects_a_cli_entry_point(self):
        self.assertTrue(uses_argparse(SCRIPTS_DIR / "consensus_client.py"))

    def test_library_module_is_not_a_cli(self):
        self.assertFalse(uses_argparse(SCRIPTS_DIR / "movement_patterns.py"))

    def test_the_word_argparse_in_a_docstring_is_not_a_cli(self):
        """Naive substring matching made this gate run itself with --help, forever."""
        tmp = Path(tempfile.mkdtemp()) / "mentions.py"
        tmp.write_text(
            '"""This module talks about argparse but does not use it."""\n'
            'NOTE = "import argparse"\n',
            encoding="utf-8",
        )
        self.assertFalse(uses_argparse(tmp))

    def test_this_gate_does_not_classify_itself_as_a_cli(self):
        self.assertFalse(uses_argparse(SCRIPTS_DIR / "check_import_health.py"))

    def test_its_own_test_file_is_not_a_cli(self):
        self.assertFalse(uses_argparse(SCRIPTS_DIR / "test_check_import_health.py"))


class TestCheckFile(unittest.TestCase):
    """check_file must actually fail on broken code, not just on missing files."""

    def _write(self, body: str) -> Path:
        tmp = Path(tempfile.mkdtemp()) / "subject.py"
        tmp.write_text(body, encoding="utf-8")
        return tmp

    def test_healthy_library_module_passes(self):
        path = self._write("VALUE = 1\n")
        ok, detail = check_file(path)
        self.assertTrue(ok, detail)

    def test_undefined_name_at_import_time_fails(self):
        path = self._write("VALUE = undefined_name_that_does_not_exist\n")
        ok, detail = check_file(path)
        self.assertFalse(ok)
        self.assertIn("NameError", detail)

    def test_missing_import_fails(self):
        path = self._write("import a_module_that_does_not_exist\n")
        ok, detail = check_file(path)
        self.assertFalse(ok)
        self.assertIn("ModuleNotFoundError", detail)

    def test_cli_whose_parser_raises_fails(self):
        path = self._write(
            "import argparse\n"
            "def main():\n"
            "    p = argparse.ArgumentParser()\n"
            "    p.add_argument('--x', type=int, choices=1)\n"  # choices must be iterable
            "    p.parse_args()\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        ok, detail = check_file(path)
        self.assertFalse(ok, "a CLI whose --help crashes must fail the gate")

    def test_silent_nonzero_exit_reports_without_crashing(self):
        """Reading the last stderr line raises IndexError when there is no output."""
        path = self._write("import sys\nsys.exit(3)\n")
        ok, detail = check_file(path)
        self.assertFalse(ok)
        self.assertTrue(detail.strip(), "a failure must carry some diagnostic")

    def test_healthy_cli_passes(self):
        path = self._write(
            "import argparse\n"
            "def main():\n"
            "    p = argparse.ArgumentParser()\n"
            "    p.add_argument('--x', type=int)\n"
            "    p.parse_args()\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        ok, detail = check_file(path)
        self.assertTrue(ok, detail)


class TestMain(unittest.TestCase):
    """main() must return 1 on every failure path, not just report it."""

    def _run_main(self, scripts, programs=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        dirs = []
        for name, files in (("scripts", scripts), ("programs", programs or {})):
            (root / name).mkdir()
            dirs.append(root / name)
            for filename, body in files.items():
                (root / name / filename).write_text(body, encoding="utf-8")
        # compileall reads sys.stdout.encoding, which a StringIO does not have.
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="utf-8", write_through=True)
        with patch.object(check_import_health, "SOURCE_DIRS", tuple(dirs)), \
                patch.object(check_import_health, "REPO_ROOT", root), \
                contextlib.redirect_stdout(output):
            rc = check_import_health.main()
        return rc, raw.getvalue().decode("utf-8")

    def test_healthy_tree_returns_zero(self):
        rc, out = self._run_main({"fine.py": "VALUE = 1\n"}, {"program.py": "VALUE = 2\n"})
        self.assertEqual(rc, 0, out)
        self.assertIn("2 modules compile and import", out)

    def test_syntax_error_returns_one(self):
        rc, out = self._run_main({"fine.py": "VALUE = 1\n", "broken.py": "def (:\n"})
        self.assertEqual(rc, 1)
        self.assertIn("failed to compile", out)

    def test_import_time_failure_returns_one_and_names_the_file(self):
        rc, out = self._run_main({"fine.py": "VALUE = 1\n"}, {"stale.py": "import no_such_module\n"})
        self.assertEqual(rc, 1)
        self.assertIn("1 of 2 modules FAILED", out)
        self.assertIn("stale.py", out)


if __name__ == "__main__":
    unittest.main()
