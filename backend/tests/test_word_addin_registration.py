from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = ROOT / "scripts" / "install-native-word-addin.ps1"
UNINSTALL_SCRIPT = ROOT / "scripts" / "uninstall-native-word-addin.ps1"
WINDOWS_ROOT = Path(os.environ.get("WINDIR", r"C:\Windows"))
POWERSHELL_32 = (
    WINDOWS_ROOT / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
)


def _child_environment(local_app_data: Path) -> dict[str, str]:
    environment: dict[str, str] = {}
    seen: set[str] = set()
    for key, value in os.environ.items():
        normalized = key.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        environment[key] = value
    environment["LOCALAPPDATA"] = str(local_app_data)
    return environment


@unittest.skipUnless(
    os.name == "nt" and POWERSHELL_32.is_file(),
    "native Word add-in registration is Windows-only",
)
class NativeWordAddinRegistrationScriptTest(unittest.TestCase):
    def test_install_relaunch_preserves_paths_with_spaces_and_apostrophes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            script_directory = (
                temporary_root / "script path; & $value (group) with 'apostrophe'"
            )
            assembly_directory = (
                temporary_root / "assembly path; & $value (group) with 'apostrophe'"
            )
            local_app_data = temporary_root / "local app data"
            script_directory.mkdir()
            assembly_directory.mkdir()
            local_app_data.mkdir()

            copied_script = script_directory / INSTALL_SCRIPT.name
            shutil.copy2(INSTALL_SCRIPT, copied_script)
            source_assembly = assembly_directory / "not-a-managed-assembly.dll"
            source_bytes = b"word-addin-relaunch-probe"
            source_assembly.write_bytes(source_bytes)

            result = subprocess.run(
                [
                    str(POWERSHELL_32),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(copied_script),
                    "-AssemblyPath",
                    str(source_assembly),
                    "-OfficePlatform",
                    "x64",
                ],
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                env=_child_environment(local_app_data),
                timeout=30,
            )

            digest = hashlib.sha256(source_bytes).hexdigest()[:12]
            installed_copy = (
                local_app_data
                / "WorkmodePublic"
                / "word-native-addin"
                / digest
                / "Workmode.WordAddin.dll"
            )
            self.assertTrue(
                installed_copy.is_file(),
                "the 64-bit child never received the complete script/assembly paths\n"
                f"exit={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertEqual(installed_copy.read_bytes(), source_bytes)
            self.assertNotEqual(
                result.returncode,
                0,
                "the deliberately invalid managed assembly must stop before registry writes",
            )

    def test_install_and_uninstall_use_path_safe_encoded_relaunches(self) -> None:
        for script in (INSTALL_SCRIPT, UNINSTALL_SCRIPT):
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                self.assertIn("-EncodedCommand", source)
                self.assertNotIn('"-File", $PSCommandPath', source)
                self.assertNotIn("Start-Process", source)
                self.assertIn("& $powerShell @arguments", source)

    def test_install_hashing_does_not_require_powershell_module_autoload(
        self,
    ) -> None:
        source = INSTALL_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Get-FileHash", source)
        self.assertIn("[System.Security.Cryptography.SHA256]::Create()", source)

    def test_registration_scripts_are_ascii_safe_for_windows_powershell_5(self) -> None:
        for script in (INSTALL_SCRIPT, UNINSTALL_SCRIPT):
            with self.subTest(script=script.name):
                try:
                    script.read_bytes().decode("ascii")
                except UnicodeDecodeError as error:
                    self.fail(
                        f"{script.name} contains source text that Windows PowerShell 5 "
                        f"can misdecode without a BOM: {error}"
                    )


if __name__ == "__main__":
    unittest.main()
