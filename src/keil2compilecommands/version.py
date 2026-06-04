from __future__ import annotations

import os
from importlib import metadata


PACKAGE_NAME = "keil2compilecommands"
DEFAULT_VERSION = "0.1.0"


def normalize_version(version: str) -> str:
    version = version.strip()
    return version[1:] if version.startswith("v") else version


def get_version() -> str:
    env_version = os.getenv("K2C_VERSION")
    if env_version:
        return normalize_version(env_version)

    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return DEFAULT_VERSION
