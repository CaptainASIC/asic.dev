#!/usr/bin/env python3
"""Repair a truncated IEND chunk in draw.io ``-e`` PNG exports (issue #8).

draw.io's CLI emits ``-e`` PNGs with the 4-byte IEND length field but missing
the 8 bytes of "IEND" type + CRC. Strict PNG decoders and vision APIs
(Anthropic included) reject the file with 400 "Could not process image".
SVG/PDF are unaffected.

Usage: python3 repair_png.py <path/to/diagram.drawio.png>

Idempotent: the ``endswith(IEND)`` guard makes this a no-op once draw.io
fixes the bug upstream, so it's safe to run unconditionally after every
``-e`` PNG export.
"""

import logging
import sys

logger = logging.getLogger(__name__)

IEND: bytes = b"\x00\x00\x00\x00IEND\xaeB`\x82"


def repair(path: str) -> bool:
    """Append a complete IEND chunk to a truncated draw.io PNG export.

    Args:
        path: Filesystem path to the ``.drawio.png`` file to repair (read and
            rewritten in place).

    Returns:
        True if the file was rewritten with a repaired IEND chunk, False if it
        already ended with a valid IEND chunk (no-op).
    """
    with open(path, "rb") as f:
        data = f.read()
    if data.endswith(IEND):
        return False
    # Reason: draw.io writes the 4-byte IEND length field then truncates; drop
    # that dangling length so the full IEND chunk we append is not duplicated.
    if data.endswith(b"\x00\x00\x00\x00"):
        data = data[:-4]
    with open(path, "wb") as f:
        f.write(data + IEND)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) != 2:
        logger.warning("usage: repair_png.py <path>")
        sys.exit(2)
    if repair(sys.argv[1]):
        print(f"repaired {sys.argv[1]}")
