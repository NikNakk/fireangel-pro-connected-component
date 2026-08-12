# Changelog

## 0.1.0-beta.23 - 2026-08-12

- Preserved Supervisor-injected environment variables through the s6-overlay
  entrypoint so authenticated Home Assistant maintenance calls can run.

## 0.1.0-beta.22 - 2026-08-12

- Switched to the Home Assistant Debian base so the bundled Arduino AVR
  toolchain has its required glibc runtime.
- Set a writable fallback `HOME` for Arduino CLI when Supervisor omits it.

## 0.1.0-beta.21 - 2026-08-12

- Made Arduino CLI use the same explicit configuration and package directory at
  image-build and runtime, preserving the installed AVR core for compilation.

## 0.1.0-beta.20 - 2026-08-12

- Forced generated GHCR image names to use the lowercase `niknakk` namespace.

## 0.1.0-beta.19 - 2026-08-12

- Limited published images to the `amd64` and `aarch64` architectures supported
  by the current Home Assistant builder workflow.

## 0.1.0-beta.18 - 2026-08-12

- Added release-bundled v1/v2 compilation for the Arduino Nano old-bootloader
  target.
- Added board discovery and safe flash/upload verification coordinated through
  authenticated Home Assistant integration maintenance services.
