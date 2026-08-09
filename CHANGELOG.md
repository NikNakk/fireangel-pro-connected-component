# Changelog

All notable changes to FireAngel Pro Connected are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.6...HEAD
[0.1.0-beta.6]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.5...v0.1.0-beta.6
[0.1.0-beta.5]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.4...v0.1.0-beta.5
[0.1.0-beta.4]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.3...v0.1.0-beta.4
[0.1.0-beta.3]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.2...v0.1.0-beta.3
[0.1.0-beta.2]: https://github.com/NikNakk/fireangel-pro-connected-component/compare/v0.1.0-beta.1...v0.1.0-beta.2
[0.1.0-beta.1]: https://github.com/NikNakk/fireangel-pro-connected-component/releases/tag/v0.1.0-beta.1
