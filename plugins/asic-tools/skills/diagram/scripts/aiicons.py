#!/usr/bin/env python3
"""Find AI / LLM brand logos (OpenAI, Claude, Gemini, ...) as draw.io styles.

draw.io's bundled shape libraries have no modern AI/LLM brand logos, so an
"LLM app architecture" renders as generic boxes. This resolves a brand name to a
draw.io `image` style that references the matching SVG from the lobe-icons set
(https://github.com/lobehub/lobe-icons, MIT) on the unpkg CDN.

  python3 aiicons.py "openai"
  python3 aiicons.py "claude" --json
  python3 aiicons.py "langchain" --variant mono --size 48

The icon is referenced by URL (data/lobe-icons.json carries only the name list,
not the assets), so draw.io fetches it from the CDN when the diagram is rendered
or opened. That means **network is required at render time**; an offline export
draws a blank box. Use --embed to fetch the SVG once and inline it as a
self-contained data URI instead (portable, no network at render time).

The logos are trademarks of their respective owners and are referenced here for
identification only — the same basis on which draw.io ships AWS/Azure icons.

Usage: python3 aiicons.py <query> [--limit N] [--variant color|mono|text]
                                  [--size PX] [--embed] [--json] [--list]
"""

import argparse
import base64
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

MANIFEST: str = os.path.join(os.path.dirname(__file__), "..", "data", "lobe-icons.json")
STYLE: str = (
    "shape=image;html=1;imageAspect=0;aspect=fixed;"
    "verticalLabelPosition=bottom;verticalAlign=top;image="
)
_VARIANT: re.Pattern[str] = re.compile(r"-(color|text)$")

# Common RAG/LLM data stores that lobe-icons lacks, mapped to simple-icons
# slugs (https://simpleicons.org, CC0). Served from the simple-icons CDN. Each
# slug below is verified to return HTTP 200 at https://cdn.simpleicons.org/<slug>.
_SIMPLEICONS_CDN: str = "https://cdn.simpleicons.org/"
_SUPPLEMENT: dict[str, str] = {
    "qdrant": "qdrant",
    "milvus": "milvus",
    "supabase": "supabase",
    "redis": "redis",
    "postgresql": "postgresql",
    "mongodb": "mongodb",
    "elasticsearch": "elasticsearch",
    "neo4j": "neo4j",
    "kafka": "apachekafka",
    "clickhouse": "clickhouse",
    "duckdb": "duckdb",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "cassandra": "apachecassandra",
    "snowflake": "snowflake",
    "databricks": "databricks",
    "mariadb": "mariadb",
    "couchbase": "couchbase",
}


def families(icons: list[str]) -> dict[str, set[str]]:
    """Group icon filenames by their base brand name.

    Args:
        icons: Icon filenames (without ``.svg``), e.g. ``["openai", "openai-text"]``.

    Returns:
        Mapping of base brand name to the set of its variant filenames.
    """
    fam: dict[str, set[str]] = {}
    for name in icons:
        base = _VARIANT.sub("", name)
        fam.setdefault(base, set()).add(name)
    return fam


def squish(s: str) -> str:
    """Lowercase a string and strip everything but ``[a-z0-9]``.

    Args:
        s: Arbitrary input string.

    Returns:
        The normalized comparison key.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def search(fam: dict[str, set[str]], query: str, limit: int) -> list[str]:
    """Rank brand bases against the query (squished + per-token matching).

    Args:
        fam: Mapping of base brand name to its variant filenames.
        query: Raw user query.
        limit: Maximum number of brand bases to return.

    Returns:
        Brand bases ordered by descending score, then name, capped at ``limit``.
    """
    q = squish(query)
    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t]
    scored: dict[str, int] = {}
    for base in fam:
        b = squish(base)
        s = 0
        # Reason: whole-query match dominates; longer/cleaner overlap scores higher
        # (exact 100 > prefix 60 > substring 40) so the best brand surfaces first.
        if q and q == b:
            s = 100
        elif q and b.startswith(q):
            s = 60
        elif q and q in b:
            s = 40
        for t in tokens:
            if t == b:
                s = max(s, 90)
            elif len(t) >= 3 and b.startswith(t):
                s = max(s, 50)
            elif len(t) >= 3 and t in b:
                s = max(s, 30)
        if s:
            scored[base] = s
    return sorted(scored, key=lambda base: (-scored[base], base))[:limit]


def search_supplement(query: str) -> str | None:
    """Fall back to the simple-icons supplement (exact or substring match).

    Args:
        query: Raw user query.

    Returns:
        The matched supplement brand key, or ``None`` if nothing matched.
    """
    q = squish(query)
    if not q:
        return None
    if q in _SUPPLEMENT:
        return q
    for brand in _SUPPLEMENT:
        if q in brand or brand in q:
            return brand
    return None


def pick_variant(base: str, variants: set[str], prefer: str) -> str | None:
    """Choose the best icon variant for a brand given a preference.

    Args:
        base: Base brand name.
        variants: Variant filenames available for the brand.
        prefer: Preferred variant, one of ``"color"``, ``"mono"``, ``"text"``.

    Returns:
        The chosen variant filename, or ``None`` if the brand has no variants.
    """
    order = {
        "color": ["-color", "", "-text"],
        "mono": ["", "-color", "-text"],
        "text": ["-text", "-color", ""],
    }[prefer]
    for suffix in order:
        cand = base + suffix
        if cand in variants:
            return cand
    return next(iter(sorted(variants)), None)


def _fetch_inline_svg(url: str, rewrite_size: bool) -> str | None:
    """Fetch an SVG and return it base64-encoded as a data URI.

    Args:
        url: SVG source URL.
        rewrite_size: If True, rewrite the ``1em`` intrinsic size so draw.io
            scales the inlined SVG.

    Returns:
        A ``data:image/svg+xml,...`` URI, or ``None`` if the fetch failed.
    """
    try:
        svg = urllib.request.urlopen(url, timeout=15).read()
    except (urllib.error.URLError, OSError) as exc:
        logger.warning("warning: could not fetch %s (%s)", url, exc)
        return None
    if rewrite_size:
        # Reason: lobe-icons declare a 1em intrinsic size; draw.io needs concrete px.
        svg = svg.replace(b'width="1em"', b'width="24"').replace(b'height="1em"', b'height="24"')
    return "data:image/svg+xml," + base64.b64encode(svg).decode()


def _resolve_lobe(
    fam: dict[str, set[str]],
    cdn: str,
    matches: list[str],
    variant: str,
    size: int,
    embed: bool,
) -> list[dict[str, object]]:
    """Build result rows for lobe-icons matches.

    Args:
        fam: Mapping of base brand name to its variant filenames.
        cdn: lobe-icons CDN base URL from the manifest.
        matches: Ranked brand bases to resolve.
        variant: Preferred variant.
        size: Cell width/height in px.
        embed: If True, inline the SVG as a data URI instead of a CDN URL.

    Returns:
        Result rows; brands whose SVG could not be fetched (when embedding) are
        skipped.
    """
    results: list[dict[str, object]] = []
    for base in matches:
        file = pick_variant(base, fam[base], variant)
        url = f"{cdn}{file}.svg"
        if embed:
            image = _fetch_inline_svg(url, rewrite_size=True)
            if image is None:
                continue
        else:
            image = url
        results.append(
            {"brand": base, "file": file, "w": size, "h": size, "style": STYLE + image},
        )
    return results


def _resolve_supplement(
    query: str,
    size: int,
    embed: bool,
) -> list[dict[str, object]]:
    """Build a result row from the simple-icons supplement, if any matches.

    Args:
        query: Raw user query.
        size: Cell width/height in px.
        embed: If True, inline the SVG as a data URI; keep the CDN URL on failure.

    Returns:
        A single-row list, or an empty list if the supplement has no match.
    """
    # Reason: lobe has no logo for this brand; fall back to simple-icons.
    brand = search_supplement(query)
    if not brand:
        return []
    slug = _SUPPLEMENT[brand]
    url = _SIMPLEICONS_CDN + slug
    image = url
    if embed:
        inlined = _fetch_inline_svg(url, rewrite_size=False)
        if inlined is not None:
            image = inlined
        else:
            logger.warning("warning: using CDN URL for %s", url)
    return [
        {
            "brand": brand,
            "file": f"simpleicons:{slug}",
            "w": size,
            "h": size,
            "style": STYLE + image,
        },
    ]


def main() -> None:
    """Parse arguments, resolve the query to draw.io styles, and print results."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(
        description="Find AI/LLM brand logos as draw.io styles (lobe-icons via CDN).",
    )
    ap.add_argument("query", nargs="?", help='brand name, e.g. "openai" or "claude"')
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--variant", choices=["color", "mono", "text"], default="color")
    ap.add_argument(
        "--size", type=int, default=48, help="cell width/height in px (icons are square)"
    )
    ap.add_argument(
        "--embed",
        action="store_true",
        help="inline the SVG as a data URI (fetches it now; portable, no network at render time)",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true", help="list all brand names and exit")
    args = ap.parse_args()

    if not os.path.exists(MANIFEST):
        sys.exit(f"error: manifest not found at {MANIFEST}")
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    fam = families(manifest["icons"])
    cdn = manifest["cdn"]

    if args.list:
        for base in sorted(fam):
            print(base)
        return
    if not args.query:
        ap.error("a query is required (or use --list)")

    matches = search(fam, args.query, args.limit)
    if matches:
        results = _resolve_lobe(fam, cdn, matches, args.variant, args.size, args.embed)
    else:
        results = _resolve_supplement(args.query, args.size, args.embed)

    if not results:
        sys.exit(
            f"no logo for {args.query!r} — for a data store try a cylinder "
            f"(shape=cylinder3) or shapesearch.py '{args.query} database'",
        )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            style = str(r["style"])
            shown = style if len(style) < 160 else style[:157] + "..."
            print(f"{r['brand']}  ({r['file']}, {r['w']}x{r['h']})\n  {shown}")


if __name__ == "__main__":
    main()
