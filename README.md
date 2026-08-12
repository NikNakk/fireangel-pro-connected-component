# FireAngel Pro Connected

A custom Home Assistant integration with maintained Arduino bridge firmware,
based on the
[original C19HOP project](https://github.com/C19HOP/WiSafe2-to-HomeAssistant-Bridge).
It communicates directly with the Arduino over USB serial; no cloud service is
involved.

This repository also contains an optional Home Assistant OS **WiSafe2 Firmware
Updater** app. It compiles and flashes the bundled
Arduino firmware while coordinating temporary serial-port maintenance with the
integration. The updater is separate from the HACS-installed integration.

The recommended legacy image is the bundled
[bug-fixed firmware](firmware/Arduino/FireAngelNano/FireAngelNano.ino).
The original C19HOP legacy firmware remains supported for existing users. The
integration also supports the bundled structured
[Protocol 2 firmware](firmware/Arduino/FireAngelNanoV2/FireAngelNanoV2.ino).
The V2 wire format is documented in the authoritative
[serial protocol specification](firmware/docs/serial-protocol-v2.md).
The integration sends no negotiation probe and automatically creates a Home
Assistant device for each unfamiliar six-digit detector ID, and keeps its
alarm, battery, base, event, model, and last-seen state up to date. Devices can
then be renamed and assigned to areas through the normal Home Assistant device
page.

Each detector also has a **Last successful test** timestamp sensor. It is empty
until that physical detector reports a test event (including `FIRE TEST`) with
a `PASS` result, and its value is retained across Home Assistant restarts.
Alarm, event, and test information reported by the bridge's own WiSafe2
interface is grouped with the serial bridge device instead of appearing as a
separate detector.

It also provides bridge buttons for sounding fire/CO test signals, silencing,
and pairing. Command acceptance only confirms that the bridge transmitted the
radio request; it does not prove that any detector received it or passed a
physical test. Command buttons remain unavailable until the firmware protocol
has been identified from incoming traffic. The
firmware's emergency simulation commands are intentionally not exposed as
buttons to reduce the risk of an accidental network-wide alarm.

## Development

Open the repository in a [development container](https://containers.dev/), then
run:

```sh
pytest
ruff check .
hass -c .devcontainer/config
```

Home Assistant is available at <http://localhost:8123>. The post-create step
links this repository's integration into the development configuration, so
source edits are picked up after restarting Home Assistant.

Without a devcontainer, create a Python virtual environment and install
`requirements-dev.txt` before running the same test and lint commands.

The two Arduino images and their shared library live under [`firmware/`](firmware/README.md).
CI compiles both images for `arduino:avr:nano:cpu=atmega328old`. These files are
kept outside `custom_components`, so HACS installs only the Home Assistant
runtime integration.

### Release versioning

The integration and firmware updater app are released independently from this
monorepo:

- Integration releases use `vX.Y.Z`, match the version in
  `custom_components/fireangel_pro_connected/manifest.json`, and create the
  GitHub Release used by HACS.
- Firmware updater app releases use `app-vX.Y.Z`, match
  `wisafe2_firmware/config.yaml`, and publish the corresponding
  `ghcr.io/niknakk/wisafe2-firmware:X.Y.Z` image without creating a GitHub
  Release.

An integration-only change therefore does not prompt an HAOS app update, and an
app-only change does not appear as a HACS integration update. Shared firmware
changes normally require an app release because the tagged firmware source is
bundled into the app image.

## Installation

### Home Assistant OS firmware updater (optional)

1. Install and configure the integration first.
2. Open **Settings → Apps → App store**, open the repository menu, and add
   `https://github.com/NikNakk/fireangel-pro-connected-component`.
3. Install **WiSafe2 Firmware Updater**.
4. Set `action`, `source`, and normally `serial_device: auto`, save, then start
   the app manually. Read the app log for the result.

See the [updater documentation](wisafe2_firmware/DOCS.md) before flashing.
Home Assistant Container/Core installations do not provide the Supervisor app
store and cannot install this updater.

### HACS

1. In HACS, open **Integrations**, select the three-dot menu, and choose
   **Custom repositories**.
2. Add `https://github.com/NikNakk/fireangel-pro-connected-component` as an
   **Integration** repository.
3. Install **FireAngel Pro Connected**, then restart Home Assistant.

### Manual

Copy `custom_components/fireangel_pro_connected` into the `custom_components`
directory in your Home Assistant configuration, then restart Home Assistant.

### Setup

1. Remove or disable any existing `serial` sensor that opens the same Arduino;
   only one process can own a serial port at a time.
2. Add **FireAngel Pro Connected** from
   **Settings → Devices & services**.
3. Enter the Arduino path shown by Home Assistant's hardware page. Prefer a
   stable `/dev/serial/by-id/...` path. Keep the default baud rate of `115200`
   for all supported firmware images. The integration identifies legacy or
   Protocol 2 traffic automatically, including after reconnection. For current
   firmware, flash either the bundled
   [bug-fixed legacy image](firmware/Arduino/FireAngelNano/FireAngelNano.ino)
   or its
   [structured Protocol V2 image](firmware/Arduino/FireAngelNanoV2/FireAngelNanoV2.ino).

The integration remembers detectors after their first message. A newly
discovered detector appears as a device named `FireAngel A1B2C3`; rename it and
assign an area from its Home Assistant device page.

## Migrating an existing YAML setup

You do not need to wait for every alarm to transmit. To import the old package
in one operation:

1. Open **Settings → Devices & services → FireAngel Pro Connected → Configure**.
2. Choose **Import legacy package YAML** and paste the complete package contents.
   Detectors with event, battery, and base-status entities are imported. The
   firmware's event-only WiSafe2 device is included, and detector types are
   inferred from legacy names containing smoke, heat, or carbon monoxide. The
   legacy entity names are also used as the detectors' initial device names;
   names you later customize in Home Assistant are not overwritten.

To add an individual detector instead:

1. Open **Settings → Devices & services → FireAngel Pro Connected → Configure**.
2. Choose **Add a detector by hex ID**.
3. Enter the six-digit ID from the old entity, such as `A1B2C3`. Colons and
   hyphens are accepted. The model code is optional and will normally be
   learned from the detector's next status or test message. Select the known
   detector type so migrated heat alarms receive the correct device class; the
   bridge firmware reports both smoke and heat events simply as `FIRE`.
4. Rename the resulting device and assign its area.

After checking the new entities, remove the old serial, template, and shell
command configuration. The integration's detector-based identifiers mirror the
old naming scheme, for example `fireangel_event_a1b2c3`.

This project extends the alarm network for monitoring and automation; it is not
a replacement for certified life-safety equipment or the alarms' native
interlink behavior.
