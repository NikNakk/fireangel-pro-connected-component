FROM ghcr.io/home-assistant/base:3.22

ARG BUILD_ARCH
ARG BUILD_VERSION
ARG ARDUINO_CLI_VERSION=1.3.1

RUN apk add --no-cache python3 py3-pyserial ca-certificates curl tar \
    && case "${BUILD_ARCH}" in \
         aarch64) cli_arch=ARM64 ;; \
         amd64) cli_arch=64bit ;; \
         armhf) cli_arch=ARMv6 ;; \
         armv7) cli_arch=ARMv7 ;; \
         i386) cli_arch=32bit ;; \
         *) echo "Unsupported architecture: ${BUILD_ARCH}" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://downloads.arduino.cc/arduino-cli/arduino-cli_${ARDUINO_CLI_VERSION}_Linux_${cli_arch}.tar.gz" \
      | tar -xz -C /usr/local/bin arduino-cli \
    && arduino-cli config init --overwrite \
    && arduino-cli core update-index \
    && arduino-cli core install arduino:avr@1.8.6

COPY app /opt/wisafe2/app
COPY firmware/Arduino /opt/wisafe2/firmware/Arduino

LABEL io.hass.name="WiSafe2 Firmware Updater" \
      io.hass.description="Compile and flash release-matched WiSafe2 bridge firmware" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      io.hass.version="${BUILD_VERSION}"

CMD ["python3", "/opt/wisafe2/app/updater.py"]
