"""Tests for the HAOS firmware updater helper."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from wisafe2_firmware.app.updater import (
    UpdaterError,
    compile_firmware,
    firmware_paths,
    flash_firmware,
    log_selected_firmware,
    resolve_serial_device,
)


def selected_firmware(source: str, tmp_path: Path):
    """Create representative bundled metadata and resolve one selection."""
    metadata = tmp_path / "firmware-versions.json"
    metadata.write_text(
        json.dumps(
            {
                "v1": {
                    "name": "Maintained legacy",
                    "version": "1.0.0",
                    "sketch": "FireAngelNano",
                },
                "v2": {
                    "name": "Protocol V2",
                    "version": "2.0.1",
                    "sketch": "FireAngelNanoV2",
                },
            }
        )
    )
    return firmware_paths(source, tmp_path / "Arduino", metadata)


def test_firmware_variants_share_release_library_tree(tmp_path: Path) -> None:
    """v1 and v2 select their named sketches and the same bundled libraries."""
    v1 = selected_firmware("v1", tmp_path)
    v2 = selected_firmware("v2", tmp_path)
    assert v1.sketch == tmp_path / "Arduino" / "FireAngelNano"
    assert v2.sketch == tmp_path / "Arduino" / "FireAngelNanoV2"
    assert v1.libraries == v2.libraries == tmp_path / "Arduino" / "libraries"
    assert (v1.name, v1.version) == ("Maintained legacy", "1.0.0")
    assert (v2.name, v2.version) == ("Protocol V2", "2.0.1")
    with pytest.raises(UpdaterError, match="Unsupported"):
        firmware_paths(
            "main", tmp_path / "Arduino", tmp_path / "firmware-versions.json"
        )


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
    paths = selected_firmware("v2", tmp_path)
    with patch("wisafe2_firmware.app.updater.run_command") as run:
        compile_firmware(paths)
    command = run.call_args.args[0]
    assert command[0:2] == ["arduino-cli", "compile"]
    assert command[-2:] == [
        "--config-file",
        "/opt/wisafe2/arduino-cli.yaml",
    ]


def test_command_supplies_home_when_supervisor_omits_it() -> None:
    """Arduino CLI receives a writable home in the app runtime."""
    from wisafe2_firmware.app.updater import run_command

    with (
        patch.dict("wisafe2_firmware.app.updater.os.environ", {}, clear=True),
        patch("wisafe2_firmware.app.updater.subprocess.run") as run,
    ):
        run_command(["arduino-cli", "version"])
    assert run.call_args.kwargs["env"]["HOME"] == "/data"


def test_selected_firmware_log_has_independent_versions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Show the metadata firmware version independently of the app version."""
    log_selected_firmware(selected_firmware("v2", tmp_path), "0.1.7")
    assert capsys.readouterr().out == (
        "Selected firmware: Protocol V2 (2.0.1)\nUpdater app version: 0.1.7\n"
    )


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
        flash_firmware(
            selected_firmware("v1", tmp_path), "/dev/ttyUSB0", client, "entry"
        )
    assert client.service.call_args_list == [
        call("suspend_for_maintenance", "entry"),
        call("resume_after_maintenance", "entry"),
    ]
    compile_mock.assert_called_once()
    assert "--verify" in run.call_args.args[0]
    assert run.call_args.args[0][-2:] == [
        "--config-file",
        "/opt/wisafe2/arduino-cli.yaml",
    ]


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
        flash_firmware(selected_firmware("v2", tmp_path), "/dev/ttyUSB0", client, None)
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
        flash_firmware(selected_firmware("v2", tmp_path), "/dev/ttyUSB0", client, None)


def test_process_level_exception_is_not_swallowed(tmp_path: Path) -> None:
    """Resume safely without converting process-level exceptions."""
    client = Mock()
    client.service.side_effect = [
        {"maintenance_suspended": True},
        {"maintenance_suspended": False, "connected": True},
    ]
    with (
        patch(
            "wisafe2_firmware.app.updater.compile_firmware",
            side_effect=KeyboardInterrupt,
        ),
        pytest.raises(KeyboardInterrupt),
    ):
        flash_firmware(selected_firmware("v2", tmp_path), "/dev/ttyUSB0", client, None)
    assert client.service.call_args_list[-1] == call("resume_after_maintenance", None)


def test_flash_tracks_stable_by_id_path_across_tty_renumber(
    tmp_path: Path,
) -> None:
    """A stable by-id link can disappear and target a new tty after upload."""
    device_dir = tmp_path / "dev" / "serial" / "by-id"
    device_dir.mkdir(parents=True)
    first_tty = tmp_path / "dev" / "ttyUSB0"
    second_tty = tmp_path / "dev" / "ttyUSB1"
    first_tty.touch()
    stable_path = device_dir / "usb-1a86_USB2.0-Serial-if00-port0"
    stable_path.symlink_to(first_tty)
    status = {"serial_device": str(stable_path)}
    assert resolve_serial_device("auto", status, device_dir) == str(stable_path)

    client = Mock()
    client.service.side_effect = [
        {"maintenance_suspended": True},
        {"maintenance_suspended": False, "connected": True},
    ]

    def upload_and_reenumerate(command: list[str]) -> None:
        assert "upload" in command
        stable_path.unlink()
        first_tty.unlink()
        second_tty.touch()
        stable_path.symlink_to(second_tty)

    with (
        patch("wisafe2_firmware.app.updater.compile_firmware"),
        patch(
            "wisafe2_firmware.app.updater.run_command",
            side_effect=upload_and_reenumerate,
        ),
    ):
        flash_firmware(
            selected_firmware("v2", tmp_path),
            str(stable_path),
            client,
            "entry",
        )

    assert stable_path.resolve() == second_tty
    assert client.service.call_args_list == [
        call("suspend_for_maintenance", "entry"),
        call("resume_after_maintenance", "entry"),
    ]
