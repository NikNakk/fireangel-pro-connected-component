# FireAngel Pro Connected

A custom Home Assistant integration for FireAngel Pro Connected.

This repository currently contains the integration scaffold. It provides a UI
config flow, lifecycle hooks, diagnostics, translations, tests, and a complete
development container. Device communication and entities can be added on top
of this foundation.

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

Copy `custom_components/fireangel_pro_connected` into the `custom_components`
directory in your Home Assistant configuration, restart Home Assistant, then
add **FireAngel Pro Connected** from **Settings → Devices & services**.

