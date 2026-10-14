# Attribution

`references/okf-0.2.md` is the **Open Knowledge Format (OKF) — Version 0.2** specification,
vendored verbatim from
[GoogleCloudPlatform/open-knowledge-format](https://github.com/GoogleCloudPlatform/open-knowledge-format),
file `SPEC.md`, pinned at commit **`ad30107c31c06aec8a7d5636e0d1058118604e6f`** (2026-08-21),
fetched 2026-10-13. 37,748 bytes, SHA-256
`26aa5da029278939f914e578107242d9607d4f2dc5fe153272b82f9ed1030101`.

Upstream is licensed **Apache License 2.0** (`LICENSE.md`). The specification text is
**unmodified**. The test fixture `tests/fixtures/conformant/computations/revenue.md` is the §10.2
example from the same file, copied verbatim. Everything else in `scripts/` and `tests/` is original
work.

v0.1 bundles are read under v0.2's own §13 fallbacks; no v0.1 copy is kept.

## Staleness

Upstream will move, and the failure is quiet: this skill would keep validating against a
specification the world has moved past. There is deliberately **no network check** in the
validator. It stays offline and deterministic.

Re-check upstream before relying on a conformance result for a new bundle:

    curl -sL "https://raw.githubusercontent.com/GoogleCloudPlatform/open-knowledge-format/main/SPEC.md" \
      | cmp - references/okf-0.2.md && echo "still current" || echo "UPSTREAM MOVED"

## Apache License 2.0 — NOTICE

Copyright Google LLC. Licensed under the Apache License, Version 2.0 (the "License"); you may not
use this file except in compliance with the License. You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied. See the License for the specific language governing permissions and limitations under the
License.
