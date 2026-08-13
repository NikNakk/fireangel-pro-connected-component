# FireAngel WiSafe2 bridge firmware

This directory contains the two maintained Arduino Nano firmware images used
with the FireAngel Pro Connected integration. Flash exactly one image; legacy
and Protocol V2 are separate build targets and do not negotiate at runtime.

- `Arduino/FireAngelNano/FireAngelNano.ino` is the bug-fixed legacy image. It preserves the
  original C19HOP serial protocol for older Home Assistant configurations.
- `Arduino/FireAngelNanoV2/FireAngelNanoV2.ino` is the structured newline-delimited JSON
  Protocol V2 image used by current versions of this integration.
- `Arduino/libraries/WiSafeRadioCore` contains the fixed-size SPI/radio decoder shared
  by both images.
- `docs/serial-protocol-v2.md` is the authoritative Protocol V2 wire contract.
- `docs/firmware-variants.md` describes compatibility and build details.
- `firmware-versions.json` is the machine-readable source of truth for the
  independently versioned firmware bundles. The generator writes both the V2
  compile-time `firmware_version.h` and the integration's firmware availability
  catalogue; regenerate them with
  `python scripts/generate_firmware_version_header.py` after changing metadata.

Both sketches target an Arduino Nano / ATmega328P at 5 V and 16 MHz. Typical
Nano-compatible boards require the `ATmega328P (Old Bootloader)` target:

```text
arduino:avr:nano:cpu=atmega328old
```

Each sketch directory matches its main `.ino` basename, so both can be compiled
directly by Arduino IDE or Arduino CLI. Both builds must include
`firmware/Arduino/libraries` through Arduino CLI's `--libraries` option or install
`WiSafeRadioCore` into the Arduino IDE sketchbook.

## Provenance

The firmware was consolidated from
[`NikNakk/WiSafe2-to-HomeAssistant-Bridge`](https://github.com/NikNakk/WiSafe2-to-HomeAssistant-Bridge),
initially from commit `83e19452c9cc2db1910a6337db2a22075383419e`. That fork is
based on the
[`C19HOP/WiSafe2-to-HomeAssistant-Bridge`](https://github.com/C19HOP/WiSafe2-to-HomeAssistant-Bridge)
project. The maintained source of truth now lives in this directory so firmware,
wire-protocol, and integration changes can be reviewed and released together.

The repository's root `LICENSE` applies to this combined project. Preserve the
upstream attribution above when redistributing the firmware.

The bridge and integration supplement the alarms' native interlink behavior.
They are not certified life-safety equipment and are not a replacement for
physical detector testing.

## Independent versions

Firmware versions do not track either the Home Assistant integration version
in `manifest.json` or the updater app version in `wisafe2_firmware/config.yaml`.
The updater reports all relevant versions directly. Legacy firmware remains
versioned in bundle metadata but does not gain a new serial message merely for
symmetry; Protocol V2 reports its version in startup and status records.
