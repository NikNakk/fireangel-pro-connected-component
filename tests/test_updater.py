"""Tests for the HAOS firmware updater helper."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from wisafe2_firmware.app.updater import (
    UpdaterError,
    compile_firmware,
    firmware_paths,
    flash_firmware,
    resolve_serial_device,
)


def test_firmware_variants_share_release_library_tree(tmp_path: Path) -> None:
    """v1 and v2 select their named sketches and the same bundled libraries."""
    v1 = firmware_paths("v1", tmp_path)
    v2 = firmware_paths("v2", tmp_path)
    assert v1.sketch == tmp_path / "FireAngelNano"
    assert v2.sketch == tmp_path / "FireAngelNanoV2"
    assert v1.libraries == v2.libraries == tmp_path / "libraries"
    with pytest.raises(UpdaterError, match="Unsupported"):
        firmware_paths("main", tmp_path)


def test_serial_resolution_explicit_integration_and_fallback(tmp_path: Path) -> None:
    """Resolution prefers explicit and integration paths and never guesses."""
    assert resolve_serial_device("/dev/ttyUSB9", None, tmp_path) == "/dev/ttyUSB9"
    assert (
        resolve_serial_device("auto", {"serial_device": "/dev/ttyUSB0"}, tmp_path)
        == "/dev/ttyUSB0"
    )
    first = tmp_path / "usb-one"
    first.touch()
    assert resolve_serial_device("auto", None, tmp_path) == str(first)
    (tmp_path / "usb-two").touch()
    with pytest.raises(UpdaterError, match="Multiple"):
        resolve_serial_device("auto", None, tmp_path)
    first.unlink()
    (tmp_path / "usb-two").unlink()
    with pytest.raises(UpdaterError, match="No FireAngel"):
        resolve_serial_device("auto", None, tmp_path)


def test_compile_does_not_call_home_assistant(tmp_path: Path) -> None:
    """Compilation invokes only Arduino CLI and does not suspend HA."""
    paths = firmware_paths("v2", tmp_path)
    with patch("wisafe2_firmware.app.updater.run_command") as run:
        compile_firmware(paths)
    assert run.call_args.args[0][0:2] == ["arduino-cli", "compile"]


def test_flash_suspends_uploads_and_resumes(tmp_path: Path) -> None:
    """A successful flash brackets tool calls with maintenance services."""
    client = Mock()
    client.service.side_effect = [
        {"maintenance_suspended": True},
        {"maintenance_suspended": False, "connected": True},
    ]
    with (
        patch("wisafe2_firmware.app.updater.compile_firmware") as compile_mock,
        patch("wisafe2_firmware.app.updater.run_command") as run,
        patch("wisafe2_firmware.app.updater.wait_for_device", return_value=True),
    ):
        flash_firmware(firmware_paths("v1", tmp_path), "/dev/ttyUSB0", client, "entry")
    assert client.service.call_args_list == [
        call("suspend_for_maintenance", "entry"),
        call("resume_after_maintenance", "entry"),
    ]
    compile_mock.assert_called_once()
    assert "--verify" in run.call_args.args[0]


def test_flash_failure_still_resumes_and_resume_failure_is_overall_failure(
    tmp_path: Path,
) -> None:
    """Upload errors trigger cleanup and restoration errors replace success."""
    client = Mock()
    client.service.side_effect = [
        {"maintenance_suspended": True},
        {"maintenance_suspended": False, "connected": True},
    ]
    with (
        patch("wisafe2_firmware.app.updater.compile_firmware"),
        patch(
            "wisafe2_firmware.app.updater.run_command",
            side_effect=subprocess.CalledProcessError(1, "arduino-cli"),
        ),
        pytest.raises(subprocess.CalledProcessError),
    ):
        flash_firmware(firmware_paths("v2", tmp_path), "/dev/ttyUSB0", client, None)
    assert client.service.call_args_list[-1] == call("resume_after_maintenance", None)

    client.service.side_effect = [
        {"maintenance_suspended": True},
        UpdaterError("Core unavailable"),
    ]
    with (
        patch("wisafe2_firmware.app.updater.compile_firmware"),
        patch("wisafe2_firmware.app.updater.run_command"),
        patch("wisafe2_firmware.app.updater.wait_for_device", return_value=True),
        pytest.raises(UpdaterError, match="flashed, but integration resume failed"),
    ):
        flash_firmware(firmware_paths("v2", tmp_path), "/dev/ttyUSB0", client, None)
