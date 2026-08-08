# Agent instructions

## Project scope

This repository contains the `fireangel_pro_connected` custom integration for
Home Assistant. It talks locally over USB serial to the Arduino firmware from
the [C19HOP WiSafe2-to-HomeAssistant Bridge](https://github.com/C19HOP/WiSafe2-to-HomeAssistant-Bridge).
Keep the integration local-only; do not introduce a cloud dependency.

The integration supplements the alarms' native interlink behavior. It is not
certified life-safety equipment. Preserve that distinction in code, UI copy,
and documentation.

## Architecture

- `custom_components/fireangel_pro_connected/bridge.py` owns the serial
  connection, protocol parsing, reconnect loop, in-memory detector state, and
  persistence of discovered detectors.
- `config_flow.py` configures the serial path and baud rate. Its options flow
  supports migration by adding detectors from six-digit hexadecimal IDs.
- `entity.py` contains common bridge and detector device-registry behavior.
- `sensor.py`, `binary_sensor.py`, and `button.py` expose Home Assistant
  entities. New detector entities must support runtime addition without an
  integration reload.
- Config-entry data stores connection settings. Config-entry options store the
  discovered/manual detector inventory. Runtime state belongs in
  `ConfigEntry.runtime_data`.
- Tests use `pytest-homeassistant-custom-component` and must not require real
  serial hardware.

## Bridge protocol

The upstream firmware normally uses `115200` baud and emits one record per
line. JSON records may contain:

- `heartBeat`: bridge heartbeat counter.
- `device`: six hexadecimal digits identifying a detector.
- `model`: four hexadecimal digits identifying a model.
- `event`: for example `FIRE TEST`, `CARBON MONOXIDE EMERGENCY`, `SILENCE`, or
  `MISSING`.
- `result`: `PASS` or `FAIL` for test events.
- `base`: `ON`, `OFF`, or `MISSING`.
- `battery`: `OK`, `LOW`, or `MISSING`.

Messages are partial updates. Never clear fields merely because a later record
omits them. The firmware also emits plain-text command and pairing responses;
retain these as the bridge's last message without treating them as detector
data. Parsing malformed or unfamiliar input must not terminate the reader.

Normalize detector IDs to uppercase six-digit hex and model codes to uppercase
four-digit hex. Do not hardcode household detector IDs. Synthetic IDs such as
`A1B2C3` are suitable for tests and examples.

The firmware collapses smoke and heat events into `FIRE`. Do not claim those
can always be inferred automatically. Preserve the manual detector-type option
so heat alarms can receive Home Assistant's heat device class. CO can be
inferred from a CO event or the known `7803` model code.

The supported outgoing commands are defined as byte constants in `const.py`.
Test, silence, and pairing commands may be exposed. Do not expose firmware
emergency-simulation commands as routine buttons or services without an
explicit user request, a strong warning, and safeguards against accidental
activation.

## Discovery and migration invariants

- The first valid message from an unfamiliar detector must create and persist
  it, notify every entity platform, and register a normal Home Assistant device
  without requiring a reload.
- A detector must use `(DOMAIN, detector_id)` as its device identifier and the
  bridge config-entry device as `via_device`.
- Detector entity unique IDs are based on the normalized detector ID. Do not
  derive identity from a user-assigned name, area, serial path, or mutable
  model.
- Manual enrollment and automatic discovery must converge on the same state
  and entity creation path. Duplicate IDs must not create duplicate devices or
  entities.
- Users own device names and area assignments in Home Assistant. Do not
  overwrite registry customizations when later messages arrive.
- Only one integration/process can own a serial port. Keep the migration docs'
  warning to disable the legacy `serial` sensor before setup.

## Home Assistant conventions

- Keep I/O asynchronous. Do not perform blocking serial reads or sleeps on the
  event loop.
- Raise `ConfigEntryNotReady` when the initial serial connection cannot be
  opened, and reconnect after later connection loss.
- Close the writer and cancel background tasks during unload.
- Use device classes, entity categories, translations, config entries, and the
  device/entity registries instead of custom state conventions where Home
  Assistant has a standard representation.
- Add all user-visible strings to both `strings.json` and
  `translations/en.json` and keep them synchronized.
- Redact credentials or tokens from diagnostics if authentication-related data
  is ever introduced.
- Pin integration requirements in `manifest.json` and mirror them in
  `requirements-dev.txt` when tests import them directly.

## Development and verification

The supported environment is `.devcontainer`, currently using Python 3.13.
The host Python may be older, so run validation inside the container when
necessary.

Before handing off a change, run:

```sh
ruff check .
ruff format --check .
pytest
```

When changing the devcontainer or Python requirements, also rebuild it:

```sh
docker build --tag fireangel-pro-connected-dev \
  --file .devcontainer/Dockerfile .
```

Tests for protocol changes should cover valid input, partial updates, malformed
input, normalization, persistence, duplicate suppression, and runtime entity
registration. Tests for outgoing commands must assert the exact bytes written.
Use mocks for the serial reader/writer; never depend on `/dev/ttyUSB0` existing
in CI.

If behavior depends on upstream firmware details, inspect the current upstream
source rather than guessing, and document any protocol inference in the change.

