from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.app_paths import APP_DATA_DIR_NAME, AppPaths
import src.startup_manager as startup_manager


class AppPathsTests(unittest.TestCase):
    def test_dev_runtime_keeps_mutable_data_in_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            local_app_data = repo / "LocalAppData"
            with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}, clear=False):
                app_paths = AppPaths.from_dirs(app_dir=repo, data_dir=repo)
                app_paths.ensure_mutable_dirs()

            self.assertEqual(app_paths.input_dir, repo / "icons-in")
            self.assertEqual(app_paths.output_dir, repo / "icons-out")
            self.assertEqual(app_paths.mappings_file, repo / "config" / "mappings.json")
            self.assertEqual(app_paths.backup_dir, local_app_data / APP_DATA_DIR_NAME / "Backups")
            self.assertEqual(app_paths.logs_dir, local_app_data / APP_DATA_DIR_NAME / "Logs")
            self.assertTrue((repo / "icons-in").is_dir())
            self.assertTrue((repo / "config" / "managed-shortcuts").is_dir())
            self.assertTrue((local_app_data / APP_DATA_DIR_NAME / "Backups").is_dir())
            self.assertTrue((local_app_data / APP_DATA_DIR_NAME / "Logs").is_dir())

    def test_frozen_runtime_uses_local_app_data_and_copies_legacy_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_dir = root / "Program Files" / "LabIcons"
            local_app_data = root / "LocalAppData"
            legacy_config = install_dir / "config"
            legacy_config.mkdir(parents=True)
            (legacy_config / "mappings.json").write_text('{"version":1,"settings":{},"mappings":[]}', encoding="utf-8")

            fake_executable = install_dir / "LabIcons.exe"
            fake_executable.parent.mkdir(parents=True, exist_ok=True)
            fake_executable.write_text("", encoding="utf-8")

            with mock.patch("sys.frozen", True, create=True), mock.patch("sys.executable", str(fake_executable)):
                with mock.patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}, clear=False):
                    app_paths = AppPaths.for_runtime()
                    app_paths.ensure_mutable_dirs()

            expected_data_dir = local_app_data / APP_DATA_DIR_NAME
            self.assertEqual(app_paths.data_dir, expected_data_dir)
            self.assertEqual(app_paths.input_dir, expected_data_dir / "icons-in")
            self.assertEqual(app_paths.output_dir, expected_data_dir / "icons-out")
            self.assertEqual(app_paths.mappings_file, expected_data_dir / "config" / "mappings.json")
            self.assertEqual(app_paths.backup_dir, local_app_data / APP_DATA_DIR_NAME / "Backups")
            self.assertEqual(app_paths.logs_dir, local_app_data / APP_DATA_DIR_NAME / "Logs")
            self.assertTrue(app_paths.mappings_file.exists())

    def test_startup_shortcut_targets_frozen_executable_directly(self) -> None:
        class FakeShell:
            def __init__(self) -> None:
                self.link = FakeLink()

            def CreateShortCut(self, _path: str) -> "FakeLink":
                return self.link

        class FakeLink:
            Targetpath = ""
            Arguments = ""
            WorkingDirectory = ""
            IconLocation = ""

            def save(self) -> None:
                pass

        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "LabIcons.exe"
            app.write_text("", encoding="utf-8")
            shell = FakeShell()

            with mock.patch("src.startup_manager._dispatch_shell", return_value=shell):
                with mock.patch("src.startup_manager.startup_shortcut_path", return_value=Path(tmp) / "Startup.lnk"):
                    with mock.patch("sys.frozen", True, create=True):
                        startup_manager.enable_startup_reapply(app)

            self.assertEqual(shell.link.Targetpath, str(app))
            self.assertEqual(shell.link.Arguments, "--reapply-once")


if __name__ == "__main__":
    unittest.main()
