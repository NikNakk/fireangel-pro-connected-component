#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
arduino_config="${ARDUINO_CONFIG_FILE:-/opt/arduino/arduino-cli.yaml}"
firmware_root="${repository_root}/firmware/Arduino"

python "${repository_root}/scripts/generate_firmware_version_header.py" --check

for sketch_name in FireAngelNano FireAngelNanoV2; do
    echo "Compiling ${sketch_name}"
    arduino-cli compile \
        --fqbn arduino:avr:nano:cpu=atmega328old \
        --libraries "${firmware_root}/libraries" \
        --config-file "${arduino_config}" \
        "${firmware_root}/${sketch_name}"
done
