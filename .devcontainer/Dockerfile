FROM mcr.microsoft.com/devcontainers/python:3.14-trixie

ARG ARDUINO_CLI_VERSION=1.3.1
ARG TARGETARCH

COPY requirements-dev.txt /tmp/requirements-dev.txt

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl \
    && case "${TARGETARCH}" in \
        amd64) \
            arduino_archive="arduino-cli_${ARDUINO_CLI_VERSION}_Linux_64bit.tar.gz"; \
            arduino_sha256="376428d7d45be640c00812a71612e1742edc2f5f9ee3742a2d6da7870e079588" \
            ;; \
        arm64) \
            arduino_archive="arduino-cli_${ARDUINO_CLI_VERSION}_Linux_ARM64.tar.gz"; \
            arduino_sha256="cf4f668b1add7a20310d79e83a1f3eb148031f95e5673d9171c65f5e9a126a94" \
            ;; \
        *) echo "Unsupported development-container architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl --fail --location --retry 5 \
        "https://downloads.arduino.cc/arduino-cli/${arduino_archive}" \
        --output "/tmp/${arduino_archive}" \
    && echo "${arduino_sha256}  /tmp/${arduino_archive}" | sha256sum --check --strict \
    && tar --extract --gzip --file "/tmp/${arduino_archive}" \
        --directory /usr/local/bin arduino-cli \
    && rm "/tmp/${arduino_archive}" \
    && mkdir --parents \
        /opt/arduino/data \
        /opt/arduino/downloads \
        /opt/arduino/user \
        /opt/arduino/build-cache \
    && arduino-cli config init --overwrite --dest-file /opt/arduino/arduino-cli.yaml \
    && arduino-cli config set directories.data /opt/arduino/data \
        --config-file /opt/arduino/arduino-cli.yaml \
    && arduino-cli config set directories.downloads /opt/arduino/downloads \
        --config-file /opt/arduino/arduino-cli.yaml \
    && arduino-cli config set directories.user /opt/arduino/user \
        --config-file /opt/arduino/arduino-cli.yaml \
    && arduino-cli config set build_cache.path /opt/arduino/build-cache \
        --config-file /opt/arduino/arduino-cli.yaml \
    && arduino-cli core update-index --config-file /opt/arduino/arduino-cli.yaml \
    && arduino-cli core install arduino:avr@1.8.6 \
        --config-file /opt/arduino/arduino-cli.yaml \
    && chown --recursive vscode:vscode /opt/arduino \
    && pip install --no-cache-dir --requirement /tmp/requirements-dev.txt \
    && rm /tmp/requirements-dev.txt \
    && apt-get clean \
    && rm --recursive --force /var/lib/apt/lists/*
