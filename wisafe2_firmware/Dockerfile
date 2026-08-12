FROM ghcr.io/home-assistant/base:3.22

ARG BUILD_ARCH
ARG BUILD_VERSION
ARG ARDUINO_CLI_VERSION=1.3.1

RUN apk add --no-cache python3 py3-pyserial ca-certificates curl tar \
    && case "${BUILD_ARCH}" in \
         aarch64) cli_arch=ARM64 ;; \
         amd64) cli_arch=64bit ;; \
         *) echo "Unsupported architecture: ${BUILD_ARCH}" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://downloads.arduino.cc/arduino-cli/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_${cli_arch}.tar.gz" \
      | tar -xz -C /usr/local/bin arduino-cli \
    && mkdir -p /opt/wisafe2/arduino-data /opt/wisafe2/arduino-downloads /opt/wisafe2/arduino-user \
    && arduino-cli config init --overwrite --dest-dir /opt/wisafe2 \
    && arduino-cli config set directories.data /opt/wisafe2/arduino-data --config-file /opt/wisafe2/arduino-cli.yaml \
    && arduino-cli config set directories.downloads /opt/wisafe2/arduino-downloads --config-file /opt/wisafe2/arduino-cli.yaml \
    && arduino-cli config set directories.user /opt/wisafe2/arduino-user --config-file /opt/wisafe2/arduino-cli.yaml \
    && arduino-cli core update-index --config-file /opt/wisafe2/arduino-cli.yaml \
    && arduino-cli core install arduino:avr@1.8.6 --config-file /opt/wisafe2/arduino-cli.yaml \
    && arduino-cli core list --config-file /opt/wisafe2/arduino-cli.yaml \
      | grep -F "arduino:avr"

COPY app /opt/wisafe2/app
COPY firmware/Arduino /opt/wisafe2/firmware/Arduino

LABEL io.hass.name="WiSafe2 Firmware Updater" \
      io.hass.description="Compile and flash release-matched WiSafe2 bridge firmware" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      io.hass.version="${BUILD_VERSION}"

CMD ["python3", "/opt/wisafe2/app/updater.py"]
