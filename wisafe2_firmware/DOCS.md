# WiSafe2 Firmware Updater

This optional Home Assistant OS app compiles or flashes the release-matched
firmware for the USB-connected WiSafe2 bridge. It does not monitor alarms or
detectors; normal serial communication remains owned by the FireAngel Pro
Connected integration.

## Supported hardware

The fixed target is an Arduino Nano with an ATmega328P, 5 V / 16 MHz and the old
bootloader (`arduino:avr:nano:cpu=atmega328old`). Other boards and bootloaders
are not supported by this first release.

Choose `v1` for the maintained legacy JSON/text protocol or `v2` for structured
Protocol 2. Both are compiled with the release's `WiSafeRadioCore` library.
Before building, the app logs the selected firmware name and version from the
bundle metadata, followed by its own independently managed app version.

## Configuration and actions

```yaml
action: compile
source: v2
serial_device: auto
```

- `board-list` prints Arduino CLI discovery, stable `/dev/serial/by-id` links,
  and the matching integration entry and port when available.
- `compile` builds only. It does not interrupt the integration.
- `flash` releases the integration's port, compiles, uploads with verification,
  waits for the path to return, and asks the integration to reconnect. Start the
  app manually each time after saving the desired action.

`serial_device: auto` first uses the port returned by the one loaded FireAngel
config entry. If the integration cannot supply one, a sole
`/dev/serial/by-id/...` device can be used for non-flashing diagnosis. Multiple
entries or devices are never guessed. Set a stable path explicitly when needed.
If multiple FireAngel config entries exist, add their `config_entry_id` to the
app options so maintenance targets the correct bridge.

Safe flashing requires a loaded FireAngel Pro Connected version that exposes
its maintenance services. After releasing the port, every failure path attempts
to resume the integration. A successful upload followed by a failed resume is
reported as a failure; inspect both app and integration logs.

## Troubleshooting

- Run `board-list` and prefer the stable `/dev/serial/by-id/...` link over a
  changing `/dev/ttyUSB0` name.
- Confirm the Nano uses the old ATmega328P bootloader. Upload synchronization
  errors commonly indicate the wrong bootloader, wrong port, a charge-only USB
  cable, a USB/serial driver problem, or another process holding the port.
- Disable any legacy Home Assistant `serial` sensor using the same device.
- After an upload the Nano resets and its path can briefly disappear. If it does
  not return, unplug/reconnect the bridge, then run `board-list` again.
- `compile` needs no serial device and is useful for separating toolchain errors
  from USB/upload errors.

## Reproducibility

The maintained source of truth remains the repository's top-level
`firmware/Arduino` directory. Release automation stages that exact tagged tree
beside the app Dockerfile and publishes a multi-architecture image whose tag
matches `config.yaml`'s app version. The running app never clones a branch or
downloads firmware. Arduino CLI 1.3.1 and Arduino AVR core 1.8.6 are pinned.

The integration version, updater app version, and Arduino firmware version are
separate release domains. `firmware/firmware-versions.json` records the bundled
firmware versions; it is not inferred from either Home Assistant component.

For Protocol V2, the integration compares the version reported by the bridge
with the released firmware catalogue and exposes the result as an advisory
firmware update entity. The entity deliberately does not start this app or
flash hardware. Update this app first, select the advertised firmware source,
and run `flash` explicitly. Legacy firmware has no version on its serial wire,
so no reliable availability comparison is possible until it is migrated.

App releases use `app-vX.Y.Z` repository tags and are independent of `vX.Y.Z`
integration releases. App tags publish container images but deliberately do not
create GitHub Releases, preventing HACS from treating an app-only release as an
integration update.

The bridge and integration supplement the alarms' native interlink behavior.
They are not certified life-safety equipment and do not replace standalone
FireAngel alarms or physical alarm testing.
