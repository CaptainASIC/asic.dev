#!/usr/bin/env python3
"""Encode a .drawio XML file into a diagrams.net browser URL.

Used as the browser fallback when the draw.io desktop CLI is unavailable.
The diagram XML is carried in the URL fragment (after ``#``), so nothing is
uploaded to any server.

Two modes:
  (default)  read-only viewer  -> https://viewer.diagrams.net/...#R<payload>
  --edit     editable editor   -> https://app.diagrams.net/...#create=<payload>

Usage: python3 encode_drawio_url.py [--edit] <path/to/input.drawio>
"""

import base64
import json
import logging
import sys
import urllib.parse
import zlib

logger = logging.getLogger(__name__)


def _deflate_b64(xml: str) -> str:
    """Percent-encode, raw-deflate, and base64 a draw.io XML payload.

    Args:
        xml: The raw .drawio XML document.

    Returns:
        Base64 of the raw-deflated, percent-encoded XML (newlines stripped),
        suitable for a diagrams.net URL fragment.
    """
    # Reason: draw.io's loader runs JS decodeURIComponent on the inflated
    # string, so the XML MUST be percent-encoded (encodeURIComponent) BEFORE
    # deflate — otherwise a literal `%` or any non-ASCII (e.g. CJK) label makes
    # the browser throw "URI malformed" and the diagram never opens.
    # encodeURIComponent leaves only A-Za-z0-9 and -_.!~*'() unescaped, which
    # `quote` reproduces here.
    pre = urllib.parse.quote(xml, safe="!~*'()")
    c = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    compressed = c.compress(pre.encode("utf-8")) + c.flush()
    # Reason: standard base64 — mxGraph's atob rejects url-safe -/_; strip newlines.
    return base64.b64encode(compressed).decode("utf-8").replace("\n", "")


def encode(xml: str) -> str:
    """Build a read-only viewer URL (mxGraph ``#R`` raw-inflate format).

    Args:
        xml: The raw .drawio XML document.

    Returns:
        A viewer.diagrams.net URL with the payload in the fragment.
    """
    return "https://viewer.diagrams.net/?tags=%7B%7D&lightbox=1&edit=_blank#R" + urllib.parse.quote(
        _deflate_b64(xml), safe=""
    )


def edit_url(xml: str) -> str:
    """Build an editable editor URL that opens directly in the draw.io editor.

    Args:
        xml: The raw .drawio XML document.

    Returns:
        An app.diagrams.net URL with a JSON ``create`` payload in the fragment.
    """
    payload = json.dumps({"type": "xml", "compressed": True, "data": _deflate_b64(xml)})
    return (
        "https://app.diagrams.net/?grid=0&pv=0&border=10&edit=_blank#create="
        + urllib.parse.quote(payload, safe="")
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = [a for a in sys.argv[1:] if a != "--edit"]
    if len(args) != 1:
        logger.warning("usage: encode_drawio_url.py [--edit] <path>")
        sys.exit(2)
    with open(args[0], encoding="utf-8") as f:
        xml = f.read()
    print(edit_url(xml) if "--edit" in sys.argv[1:] else encode(xml))
