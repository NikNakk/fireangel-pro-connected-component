"""Compile and flash release-bundled WiSafe2 bridge firmware."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FQBN = "arduino:avr:nano:cpu=atmega328old"
FIRMWARE_ROOT = Path("/opt/wisafe2/firmware/Arduino")
OPTIONS_PATH = Path("/data/options.json")
CORE_API = "http://supervisor/core/api"
DOMAIN = "fireangel_pro_connected"
SOURCE_SKETCHES = {"v1": "FireAngelNano", "v2": "FireAngelNanoV2"}


class UpdaterError(RuntimeError):
    """A user-actionable updater failure."""


@dataclass(frozen=True)
class FirmwarePaths:
    """Selected release-bundled firmware paths."""

    sketch: Path
    libraries: Path


def firmware_paths(source: str, root: Path = FIRMWARE_ROOT) -> FirmwarePaths:
    """Resolve a supported firmware variant without accepting arbitrary paths."""
    try:
        sketch = root / SOURCE_SKETCHES[source]
    except KeyError as err:
        raise UpdaterError(f"Unsupported firmware source: {source}") from err
    return FirmwarePaths(sketch=sketch, libraries=root / "libraries")


class HomeAssistantClient:
    """Call the integration through Supervisor's authenticated Core proxy."""

    def __init__(self, token: str, timeout: float = 30) -> None:
        self.token = token
        self.timeout = timeout

    def service(
        self, service: str, config_entry_id: str | None = None
    ) -> dict[str, Any]:
        payload = {} if not config_entry_id else {"config_entry_id": config_entry_id}
        request = urllib.request.Request(
            f"{CORE_API}/services/{DOMAIN}/{service}?return_response",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as err:
            raise UpdaterError(
                f"Home Assistant service {service} failed: {err}"
            ) from err
        if isinstance(result, dict) and "service_response" in result:
            result = result["service_response"]
        if not isinstance(result, dict):
            raise UpdaterError(f"Home Assistant service {service} returned no response")
        return result


def resolve_serial_device(
    configured: str,
    status: dict[str, Any] | None,
    by_id_dir: Path = Path("/dev/serial/by-id"),
) -> str:
    """Resolve an explicit, integration-owned, or sole stable serial device."""
    if configured != "auto":
        return configured
    if status and status.get("serial_device"):
        return str(status["serial_device"])
    devices = sorted(by_id_dir.glob("*")) if by_id_dir.is_dir() else []
    if len(devices) == 1:
        return str(devices[0])
    if not devices:
        raise UpdaterError(
            "No FireAngel config entry or /dev/serial/by-id device found"
        )
    raise UpdaterError("Multiple /dev/serial/by-id devices found; set serial_device")


def run_command(command: list[str]) -> None:
    """Run one tool command with output streamed to the add-on log."""
    subprocess.run(command, check=True)


def compile_firmware(paths: FirmwarePaths) -> None:
    """Compile the selected sketch against its bundled shared libraries."""
    run_command(
        [
            "arduino-cli",
            "compile",
            "--fqbn",
            FQBN,
            "--libraries",
            str(paths.libraries),
            str(paths.sketch),
        ]
    )


def wait_for_device(device: str, timeout: float = 30) -> bool:
    """Wait for a serial path to exist after the Nano resets."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if Path(device).exists():
            return True
        time.sleep(0.5)
    return False


def wait_for_integration(
    client: HomeAssistantClient,
    config_entry_id: str | None,
    initial: dict[str, Any],
    timeout: float = 45,
) -> bool:
    """Wait until Home Assistant confirms normal serial communication returned."""
    if initial.get("connected") and not initial.get("maintenance_suspended"):
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        status = client.service("maintenance_status", config_entry_id)
        if status.get("connected") and not status.get("maintenance_suspended"):
            return True
    return False


def flash_firmware(
    paths: FirmwarePaths,
    device: str,
    client: HomeAssistantClient,
    config_entry_id: str | None,
) -> None:
    """Suspend the integration, compile/upload/verify, and always resume it."""
    suspended = False
    flash_error: BaseException | None = None
    try:
        client.service("suspend_for_maintenance", config_entry_id)
        suspended = True
        compile_firmware(paths)
        run_command(
            [
                "arduino-cli",
                "upload",
                "--verify",
                "--fqbn",
                FQBN,
                "--port",
                device,
                str(paths.sketch),
            ]
        )
        if not wait_for_device(device):
            raise UpdaterError(
                f"Serial device did not reappear within 30 seconds: {device}"
            )
    except BaseException as err:
        flash_error = err
    finally:
        if suspended:
            try:
                result = client.service("resume_after_maintenance", config_entry_id)
                if result.get("maintenance_suspended"):
                    raise UpdaterError("Integration remained suspended after resume")
                if not wait_for_integration(client, config_entry_id, result):
                    raise UpdaterError(
                        "Integration did not reconnect within 45 seconds after flashing"
                    )
            except BaseException as resume_error:
                if flash_error is not None:
                    raise UpdaterError(
                        f"Firmware operation failed ({flash_error}); integration "
                        f"resume also failed: {resume_error}"
                    ) from resume_error
                raise UpdaterError(
                    f"Firmware flashed, but integration resume failed: {resume_error}"
                ) from resume_error
    if flash_error is not None:
        raise flash_error


def main() -> int:
    """Execute the configured one-shot add-on action."""
    options = json.loads(OPTIONS_PATH.read_text())
    action = options.get("action", "compile")
    source = options.get("source", "v2")
    configured_device = options.get("serial_device", "auto")
    config_entry_id = options.get("config_entry_id") or None
    paths = firmware_paths(source)
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    client = HomeAssistantClient(token) if token else None

    status = None
    if client is not None:
        try:
            status = client.service("maintenance_status", config_entry_id)
            print(
                "FireAngel entry: "
                f"{status.get('title')} ({status.get('config_entry_id')}); "
                f"port={status.get('serial_device')}; "
                f"connected={status.get('connected')}"
            )
        except UpdaterError:
            if action == "flash":
                raise

    if action == "board-list":
        run_command(["arduino-cli", "board", "list"])
        by_id = Path("/dev/serial/by-id")
        print("/dev/serial/by-id devices:")
        for device in sorted(by_id.glob("*")) if by_id.is_dir() else []:
            print(f"  {device} -> {device.resolve()}")
        return 0
    if action == "compile":
        compile_firmware(paths)
        print(f"Firmware {source} compiled successfully")
        return 0
    if action != "flash":
        raise UpdaterError(f"Unsupported action: {action}")
    if client is None:
        raise UpdaterError(
            "SUPERVISOR_TOKEN is unavailable; safe flashing is not possible"
        )
    device = resolve_serial_device(configured_device, status)
    flash_firmware(paths, device, client, config_entry_id)
    print(
        f"Firmware {source} flashed and integration resume was requested successfully"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UpdaterError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
