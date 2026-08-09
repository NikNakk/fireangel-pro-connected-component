# FireAngel Pro Connected

A custom Home Assistant integration for the
[C19HOP WiSafe2-to-HomeAssistant Bridge](https://github.com/C19HOP/WiSafe2-to-HomeAssistant-Bridge).
It communicates directly with the Arduino over USB serial; no cloud service is
involved.

The integration reads the bridge's JSON messages, automatically creates a Home
Assistant device for each unfamiliar six-digit detector ID, and keeps its
alarm, battery, base, event, model, and last-seen state up to date. Devices can
then be renamed and assigned to areas through the normal Home Assistant device
page.

It also provides bridge buttons for fire/CO tests, silencing, and pairing. The
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

## Installation

1. Copy `custom_components/fireangel_pro_connected` into the
   `custom_components` directory in your Home Assistant configuration.
2. Remove or disable any existing `serial` sensor that opens the same Arduino;
   only one process can own a serial port at a time.
3. Restart Home Assistant, then add **FireAngel Pro Connected** from
   **Settings → Devices & services**.
4. Enter the Arduino path shown by Home Assistant's hardware page. Prefer a
   stable `/dev/serial/by-id/...` path. Keep the default baud rate of `115200`
   for the upstream firmware.

The integration remembers detectors after their first message. A newly
discovered detector appears as a device named `FireAngel A1B2C3`; rename it and
assign an area from its Home Assistant device page.

## Migrating an existing YAML setup

You do not need to wait for every alarm to transmit. To import the old package
in one operation:

1. Open **Settings → Devices & services → FireAngel Pro Connected → Configure**.
2. Choose **Import legacy package YAML** and paste the complete package contents.
   Detectors with event, battery, and base-status entities are imported. The
   firmware's event-only pseudo-device is ignored, and detector types are
   inferred from legacy names containing smoke, heat, or carbon monoxide.

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
