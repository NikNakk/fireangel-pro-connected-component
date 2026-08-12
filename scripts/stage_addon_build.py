"""Create the add-on Docker context from the repository's firmware source."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def stage(repository: Path, destination: Path) -> None:
    """Build a clean context containing add-on code and release firmware."""
    addon = repository / "wisafe2_firmware"
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("Dockerfile", "app"):
        source = addon / name
        target = destination / name
        shutil.copytree(source, target) if source.is_dir() else shutil.copy2(
            source, target
        )
    shutil.copytree(repository / "firmware", destination / "firmware")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    stage(Path(__file__).resolve().parents[1], args.destination.resolve())
