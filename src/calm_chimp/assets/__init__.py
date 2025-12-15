from __future__ import annotations

from importlib import resources


def asset_path(relative: str) -> str:
    """Return an absolute path for a bundled asset."""

    return str(resources.files(__name__).joinpath(relative))
