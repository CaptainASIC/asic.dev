#!/usr/bin/env python3
"""Search 10k+ official draw.io shapes for their exact style strings.

Resolves a keyword query (e.g. "aws lambda", "uml actor", "k8s pod") to the
matching palette shapes so a diagram can use the real draw.io `style=` string
instead of a hand-guessed one. Covers AWS / Azure / GCP / Cisco / Kubernetes /
UML / BPMN / P&ID / electrical / flowchart / network / general shape sets.

Based on the search in jgraph/drawio-mcp (Apache-2.0): tag map with exact +
Soundex matching, strict AND first, scored OR fallback. The matched set is
identical to upstream; the one addition is a tiebreaker that, among shapes with
the same tag score, prefers ones whose title contains the query terms verbatim
(so "dynamodb" returns the shape titled "DynamoDB", not a neighbor merely tagged
with it). The bundled index (data/shape-index.json.gz) is the upstream draw.io
shape data — see data/SHAPE-INDEX-NOTICE.md.

Usage:
  python3 shapesearch.py "aws lambda" [--limit N] [--json]
"""

import argparse
import gzip
import json
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

INDEX: str = os.path.join(os.path.dirname(__file__), "..", "data", "shape-index.json.gz")
_SOUNDEX_MAP: str = "01230120022455012603010202"  # A..Z digit codes
_TRAIL: re.Pattern[str] = re.compile(r"\.*\d*$")  # strip trailing digits/dots before soundex


def soundex(name: str) -> str:
    """Compute the 4-character Soundex code for a token.

    Args:
        name: Token to encode.

    Returns:
        The Soundex code, or an empty string for empty input.
    """
    if not name:
        return ""
    s = [name[0].upper()]
    si = 1
    for ch in name[1:]:
        c = ord(ch.upper()) - 65
        if 0 <= c <= 25 and _SOUNDEX_MAP[c] != "0":
            code = _SOUNDEX_MAP[c]
            if code != s[si - 1]:
                s.append(code)
                si += 1
                if si > 3:
                    break
    s += ["0"] * (4 - len(s))
    return "".join(s[:4])


def build_tag_map(shapes: list[dict[str, object]]) -> dict[str, set[int]]:
    """Index shapes by tag token and the Soundex of each tag token.

    Args:
        shapes: Parsed shape records, each with an optional ``tags`` string.

    Returns:
        Mapping of tag (and its Soundex) to the set of shape indices.
    """
    tag_map: dict[str, set[int]] = {}
    for i, shape in enumerate(shapes):
        raw = shape.get("tags")
        if not raw:
            continue
        seen: set[str] = set()
        for token in re.sub(r"[/,()]", " ", str(raw).lower()).split(" "):
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            tag_map.setdefault(token, set()).add(i)
            sx = soundex(_TRAIL.sub("", token))
            if sx and sx != token and sx not in seen:
                seen.add(sx)
                tag_map.setdefault(sx, set()).add(i)
    return tag_map


def split_compound(token: str) -> list[str]:
    """Split a compound token into its parts.

    Examples: ``'pid2misc' -> ['pid', 'misc']``; ``'discInst' -> ['disc', 'inst']``.

    Args:
        token: Raw query token, possibly camelCase or digit-joined.

    Returns:
        The component sub-tokens of length >= 2.
    """
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", token)
    spaced = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", spaced)
    spaced = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", spaced)
    return [p for p in spaced.lower().split() if len(p) >= 2]


def match_term(tag_map: dict[str, set[int]], term: str) -> tuple[set[int], set[int]]:
    """Resolve a single term to its exact and Soundex-only shape matches.

    Args:
        tag_map: Tag index from ``build_tag_map``.
        term: A single normalized query term.

    Returns:
        A ``(exact, phonetic)`` pair of shape-index sets; ``phonetic`` excludes
        anything already in ``exact``.
    """
    exact = set(tag_map.get(term, set()))
    phonetic: set[int] = set()
    sx = soundex(_TRAIL.sub("", term))
    if sx and sx != term:
        phonetic = {i for i in tag_map.get(sx, set()) if i not in exact}
    return exact, phonetic


def _normalize_terms(query: str) -> list[str]:
    """Expand a raw query into deduplicated, compound-split search terms.

    Args:
        query: Raw user query.

    Returns:
        Ordered, deduplicated search terms.
    """
    terms: list[str] = []
    seen: set[str] = set()
    for raw in query.lower().split():
        subs = split_compound(raw) or ([raw] if len(raw) >= 2 else [])
        for t in subs:
            if t not in seen:
                seen.add(t)
                terms.append(t)
    return terms


def _score_matches(
    term_matches: list[tuple[set[int], set[int]]],
) -> dict[int, float]:
    """Score shapes from per-term matches: strict AND if non-empty, else OR.

    Args:
        term_matches: One ``(exact, phonetic)`` pair per query term.

    Returns:
        Mapping of shape index to score (+1.0 per exact term, +0.5 per
        Soundex-only term), restricted to the AND set when one exists.
    """
    # Reason: require every term to hit some shape first (strict AND); only if
    # that yields nothing do we fall back to scoring the union (OR).
    and_set: set[int] | None = None
    for exact, phonetic in term_matches:
        combined = exact | phonetic
        and_set = combined if and_set is None else (and_set & combined)
        if not and_set:
            break

    scores: dict[int, float] = {}
    pool = and_set if and_set else None
    for exact, phonetic in term_matches:
        for idx in exact:
            if pool is None or idx in pool:
                scores[idx] = scores.get(idx, 0) + 1.0
        for idx in phonetic:
            if (pool is None or idx in pool) and idx not in exact:
                scores[idx] = scores.get(idx, 0) + 0.5
    return scores


def search(
    shapes: list[dict[str, object]],
    tag_map: dict[str, set[int]],
    query: str,
    limit: int,
) -> list[dict[str, object]]:
    """Rank shapes for a query and return the top results.

    Args:
        shapes: Parsed shape records.
        tag_map: Tag index from ``build_tag_map``.
        query: Raw user query.
        limit: Maximum number of results to return.

    Returns:
        Result rows (``style``/``w``/``h``/``title``) ordered best-first.
    """
    if not query:
        return []
    terms = _normalize_terms(query)
    if not terms:
        return []

    term_matches = [match_term(tag_map, t) for t in terms]
    scores = _score_matches(term_matches)

    # Reason: rank by tag score desc, then by how many query terms appear verbatim
    # in the title, then casefolded title, then index. The title-hit tiebreak (our
    # one addition over upstream) only reorders *within* an equal tag-score group,
    # so e.g. the shape literally titled "DynamoDB" ranks above a neighbor that is
    # merely tagged `dynamodb` (like "Attribute"). The trailing index keeps ties
    # deterministic.
    term_set = set(terms)

    def title_hits(idx: int) -> int:
        toks = set(re.split(r"[^a-z0-9]+", str(shapes[idx].get("title", "")).casefold()))
        return len(term_set & toks)

    ranked = sorted(
        scores,
        key=lambda i: (-scores[i], -title_hits(i), str(shapes[i].get("title", "")).casefold(), i),
    )
    return [
        {
            "style": shapes[i]["style"],
            "w": shapes[i]["w"],
            "h": shapes[i]["h"],
            "title": shapes[i]["title"],
        }
        for i in ranked[:limit]
    ]


def main() -> None:
    """Parse arguments, search the shape index, and print matching styles."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(
        description="Search official draw.io shapes for their style strings.",
    )
    ap.add_argument("query", help='keywords, e.g. "aws lambda" or "uml actor"')
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    if not os.path.exists(INDEX):
        sys.exit(f"error: shape index not found at {INDEX}")
    with gzip.open(INDEX, "rt", encoding="utf-8") as f:
        shapes = json.load(f)

    results = search(shapes, build_tag_map(shapes), args.query, args.limit)
    if not results:
        sys.exit(f"no shapes matched {args.query!r}")
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"{r['title']}  ({r['w']}x{r['h']})\n  {r['style']}")


if __name__ == "__main__":
    main()
