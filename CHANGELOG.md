# Changelog

All notable changes to FireAngel Pro Connected are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0-beta.14] - 2026-08-11

### Fixed

- Resized the bundled integration icon to Home Assistant's standard 256-pixel
  size and added a 512-pixel high-DPI variant for sharper display.

### Changed

- Replaced the diagnostic **Last message** entity's raw JSON state with a short
  protocol-aware summary, retained the full line as an attribute and in
  diagnostics, and disabled the entity by default for new installations.

## [0.1.0-beta.13] - 2026-08-11

### Added

- Added a diagnostic **Activity** binary sensor that remains on while valid
  bridge traffic has been received recently, showing heartbeat health without
  recording a new timestamp for every keepalive.

### Changed

- Excluded legacy and Protocol 2 heartbeat payloads from the **Last message**
  sensor to avoid periodic recorder entries when no meaningful event occurred.

## [0.1.0-beta.12] - 2026-08-11

### Added

- Added passive runtime detection and full command/event support for the
  structured Protocol 2 firmware while retaining original and improved legacy
  firmware support.

### Changed

- Renamed test command buttons to **Sound … test signal** and clarified that
  command acceptance is not evidence of detector receipt or a successful
  physical detector test. Bridge-generated legacy `PASS` actions no longer
  update detector test timestamps.
- Extended diagnostics with detected protocol, firmware/radio state, uptime,
  command/error details, heartbeat and general activity times, and validated
  firmware counters. General activity is refreshed by valid traffic because
  firmware heartbeats are only emitted while the bridge is otherwise idle.
- Based entity availability on recognized activity within 75 seconds and
  serialized management commands while pairing is active for both protocols.
  Correlated V2 busy errors and legacy `CMD BUSY` responses remain diagnostic
  command outcomes.
- Simplified diagnostics output now that the integration stores no credentials
  or tokens requiring redaction.

## [0.1.0-beta.11] - 2026-08-10

### Fixed

- Identified model code `1104` as the FP1720W2 heat alarm and updated existing
  Home Assistant device records when a detector's model is learned after its
  initial registration.

## [0.1.0-beta.10] - 2026-08-10

### Changed

- Grouped the configured bridge WiSafe2 interface's alarm, event, last-test,
  and model-code entities with the serial bridge device instead of registering
  a separate detector device.

### Fixed

- Reconciled the divergent beta.8 and beta.9 release histories so beta.8's
  detector classification and bridge-device behavior remain available alongside
  the last-successful-test timestamp introduced in beta.9.

## [0.1.0-beta.9] - 2026-08-10

### Added

- Added a **Last successful test** timestamp sensor for every detector, updated
  only by passing test events and persisted across Home Assistant restarts.

## [0.1.0-beta.8] - 2026-08-09

### Added

- Added a disabled-by-default diagnostic **Model code** sensor to each detector
  so unknown four-digit WiSafe2 model codes can be identified.

### Changed

- Identified the Arduino bridge's harvested WiSafe2 device by a configurable
  six-digit ID instead of its donor device's model code. New setups default to
  the original firmware ID `A5B813`; existing setups use the same default.

### Fixed

- Classified known smoke and carbon-monoxide models automatically while
  retaining manual heat-alarm selection. Definitive carbon-monoxide events,
  known CO model codes, and the configured bridge ID override a manual or
  legacy-imported smoke or heat type.
- Stopped creating meaningless battery and base-status entities for the
  configured bridge WiSafe2 device. Its alarm and test-event reporting remain
  available, with event icons reflecting smoke, heat, carbon-monoxide, or
  bridge-interface types. Previously registered bridge battery and base-status
  entities are removed on upgrade.

## [0.1.0-beta.7] - 2026-08-09

### Fixed

- Persisted each detector's latest event, test result, battery condition, and
  base condition so entity status survives Home Assistant restarts until the
  Arduino reports a change. Runtime status is kept in integration storage,
  separate from user-owned config-entry options.
- Included the bridge's event-only WiSafe2 device in bulk legacy YAML imports
  instead of waiting for it to be rediscovered after setup.

### Changed

- Renamed detector **Base problem** entities to **Base status**. Their standard
  Home Assistant problem states remain **OK** when the detector reports `ON`
  and **Problem** when it reports `OFF` or `MISSING`.

## [0.1.0-beta.6] - 2026-08-09

### Added

- Added this changelog and repository guidance to keep it current for future
  user-visible changes and releases.

### Changed

- Updated the integration icon to use a transparent outer background with a
  fitted white rim, improving its appearance alongside other Home Assistant
  integration icons and on dark backgrounds.
- Renamed detector battery entities from **Battery low** to **Battery**. The
  entities retain their Home Assistant battery binary-sensor behavior and
  existing unique IDs.

## [0.1.0-beta.5] - 2026-08-09

### Fixed

- Made firmware field parsing case-insensitive, including detector identifiers,
  so messages using keys such as `Device` are handled like their lowercase
  equivalents.
- Added coverage for mixed-case firmware messages.

## [0.1.0-beta.4] - 2026-08-09

### Added

- Imported legacy entity names as initial detector device names during bulk
  YAML migration.
- Expanded config-flow and migration test coverage, including invalid and
  duplicate input cases.

### Changed

- Preserved Home Assistant device-registry names once users customize them.
- Refined ignored development and test artifacts.

## [0.1.0-beta.3] - 2026-08-09

### Changed

- Updated the GitHub Actions used by continuous integration and release
  workflows.
- Removed an unsupported key from the integration manifest.

## [0.1.0-beta.2] - 2026-08-09

### Changed

- Updated the development container configuration and editor integration for
  the supported development environment.

## [0.1.0-beta.1] - 2026-08-09

### Added

- Added the initial local-only Home Assistant integration for the C19HOP
  WiSafe2-to-HomeAssistant USB serial bridge.
- Added asynchronous serial connection handling, line-oriented protocol
  parsing, reconnect behavior, and clean unloading.
- Added automatic detector discovery and persistence, plus runtime entity and
  device registration without requiring an integration reload.
- Added alarm, battery, base-status, last-event, bridge-message, and connection
  entities using Home Assistant device classes and device-registry hierarchy.
- Added controls for alarm tests, silencing, checking pairing, and starting
  pairing. Firmware emergency-simulation commands are intentionally excluded.
- Added configuration for the serial path and baud rate, individual detector
  enrollment by hexadecimal ID, manual detector-type selection, and bulk
  migration from legacy YAML packages.
- Added model-name mapping and automatic carbon-monoxide detection from events
  and the known `7803` model code.
- Added diagnostics with config-entry data redaction support.
- Added English translations, documentation, a development container, tests,
  lint configuration, continuous integration, and release automation.
- Added HACS metadata, installation instructions, and the original integration
  icon.

[Unreleased]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.14...HEAD
[0.1.0-beta.14]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.13...v0.1.0-beta.14
[0.1.0-beta.13]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.12...v0.1.0-beta.13
[0.1.0-beta.12]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.11...v0.1.0-beta.12
[0.1.0-beta.11]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.10...v0.1.0-beta.11
[0.1.0-beta.10]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.9...v0.1.0-beta.10
[0.1.0-beta.9]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.8...v0.1.0-beta.9
[0.1.0-beta.8]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.7...v0.1.0-beta.8
[0.1.0-beta.7]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.6...v0.1.0-beta.7
[0.1.0-beta.6]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.5...v0.1.0-beta.6
[0.1.0-beta.5]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.4...v0.1.0-beta.5
[0.1.0-beta.4]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.3...v0.1.0-beta.4
[0.1.0-beta.3]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.2...v0.1.0-beta.3
[0.1.0-beta.2]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.1...v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/NikNakk/fireangel-pro-connected-component/releases/tag/v0.1.0-beta.1
