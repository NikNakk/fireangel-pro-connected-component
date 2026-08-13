# Agent instructions

## Project scope

This repository contains the `fireangel_pro_connected` custom integration for
Home Assistant and its locally connected Arduino bridge firmware. The bundled
`firmware/Arduino/FireAngelNano/` is the maintained legacy implementation,
`firmware/Arduino/FireAngelNanoV2/` is the structured V2 implementation,
`firmware/Arduino/libraries/WiSafeRadioCore/` is their shared radio core, and
`firmware/docs/serial-protocol-v2.md` is the authoritative Protocol 2
specification. The firmware is based on the
[original C19HOP project](https://github.com/C19HOP/WiSafe2-to-HomeAssistant-Bridge),
whose legacy firmware remains a supported compatibility target.
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

## Bridge protocols

All supported firmware normally uses `115200` baud and emits one record per
line. The maintained legacy reference is the bundled bug-fixed
`firmware/Arduino/FireAngelNano/` image; the original C19HOP legacy image
remains supported. Legacy JSON records may contain:

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

The legacy firmware collapses smoke and heat events into `FIRE`. Do not claim those
can always be inferred automatically. Preserve the manual detector-type option
so heat alarms can receive Home Assistant's heat device class. CO can be
inferred from a CO event or the known `7803` model code.

Protocol 2 is defined by `firmware/docs/serial-protocol-v2.md`; inspect that
document and `firmware/Arduino/FireAngelNanoV2/FireAngelNanoV2.ino` before
changing V2 parsing or command encoding. V2 commands are compact JSON objects
containing `command` and an optional unsigned 16-bit `id`; `type` is used for
firmware-to-host messages and must not be added to host-to-firmware command
objects.

The supported outgoing semantic commands and protocol mappings are defined in
`const.py`. Test, silence, and pairing commands may be exposed. Do not expose firmware
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

The supported environment is `.devcontainer`, currently using Python 3.14.
The host Python may be older, so run validation inside the container when
necessary.

When using an execution sandbox, run `pytest` with sandbox escalation. The
sandbox blocks the socket operations used by asyncio's internal self-pipe,
which causes the test suite to hang rather than report a failure. Ruff does not
require escalation.

Before handing off a change, run:

```sh
ruff check .
ruff format --check .
pytest
```

When firmware changes, compile both bundled images for
`arduino:avr:nano:cpu=atmega328old` with `firmware/Arduino/libraries` available
through Arduino CLI's `--libraries` option. Both sketch directories match their
main `.ino` basenames and compile directly. In the devcontainer, run
`scripts/compile_firmware.sh`. Report flash and SRAM usage.

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

If behavior depends on firmware details, inspect the bundled firmware rather
than guessing. Treat `firmware/Arduino/FireAngelNano/` as authoritative for
maintained legacy behavior and the bundled V2 protocol document and
`FireAngelNanoV2` parser as authoritative for Protocol 2. Inspect the original
C19HOP source when verifying backward compatibility, and document any remaining
protocol inference in the change.

Keep firmware sources and build-only files outside `custom_components/`; HACS
must install only the runtime integration.

## Changelog

- Keep the root `CHANGELOG.md` updated for user-visible integration, shared
  firmware, and repository changes. Keep `wisafe2_firmware/CHANGELOG.md`
  updated for user-visible firmware updater app changes.
- Add pending changes under `Unreleased`, using the Keep a Changelog categories
  `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, or `Security` as
  appropriate.
- When preparing a release, move the pending entries into a versioned section
  with its release date and update the comparison links at the bottom of the
  file.
- Call out breaking changes, migration steps, and safety-relevant behavior
  explicitly. Do not add routine formatting or test-only changes unless they
  materially affect users or contributors.

## Release publishing

- Maintain three independent version domains: the integration version in
  `manifest.json`, the updater app version in `wisafe2_firmware/config.yaml`,
  and firmware bundle versions in `firmware/firmware-versions.json`. Never
  force them to match. After changing the V2 firmware version metadata,
  regenerate its compile-time header and integration availability catalogue with
  `python scripts/generate_firmware_version_header.py` and validate it with
  the same command plus `--check`.
- The firmware update entity is advisory and Protocol V2-only because legacy
  firmware does not report its installed version. Do not infer a legacy
  version or initiate physical-device flashing from the entity. Publish the
  updater app containing new firmware before releasing integration metadata
  that advertises it.
- The integration and firmware updater app are versioned independently even
  though they share this repository. Do not bump or publish the unaffected
  component merely because the other one changed.
- For an integration release, update
  `custom_components/fireangel_pro_connected/manifest.json` and the root
  `CHANGELOG.md`, then create an annotated `vX.Y.Z` tag. The
  `integration-release.yml` workflow validates that the tag matches the
  manifest and creates the GitHub Release consumed by HACS. It does not publish
  an updater app image.
- For a firmware updater app release, update `wisafe2_firmware/config.yaml` and
  `wisafe2_firmware/CHANGELOG.md`, then create an annotated `app-vX.Y.Z` tag.
  The `app-release.yml` workflow validates that the tag matches the app config
  and publishes `ghcr.io/niknakk/wisafe2-firmware:X.Y.Z`. It intentionally does
  not create a GitHub Release, so HACS does not mistake an app version for an
  integration update.
- App release source, including bundled firmware, is taken from the exact
  `app-vX.Y.Z` tag. Commit the app version to `main` before tagging, and do not
  announce the update as available until the image workflow succeeds; the app
  store can observe the new config version before its image finishes publishing.
- A change spanning both components may update both versions and changelogs and
  use both tag forms. Shared firmware changes normally require an app release
  because firmware is bundled into that image, but require an integration
  release only when integration behavior or compatibility also changes.
- Publishing either release requires committing the prepared release on
  `main`, creating the appropriate annotated tag, and pushing both `main` and
  that tag to `origin`.
- Do not require GitHub CLI authentication or create a pull request. Do not
  manually publish a GitHub Release unless the user explicitly requests it;
  pushing an integration tag triggers that publication automatically, while
  app tags must remain tag-and-image releases only.
