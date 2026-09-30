"""Bounded reads and atomic, non-overwriting desktop exports."""

import os
from pathlib import Path
import tempfile


def read_bounded(path, limit):
    with Path(path).open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f'File exceeds the {limit:,}-byte limit.')
    return data


def export_new(path, data):
    """Publish a complete file without replacing an existing destination.

    A same-directory hard link makes publication atomic and exclusive. Unsupported
    filesystems fail closed; the caller can choose another destination.
    """
    target = Path(path)
    descriptor, staging = tempfile.mkstemp(prefix='.cipher-vault-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(staging, target)
    finally:
        Path(staging).unlink(missing_ok=True)
