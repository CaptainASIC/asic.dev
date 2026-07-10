# Attribution

`references/okf-0.1.md` is the **Open Knowledge Format (OKF) v0.1 — Draft** specification, vendored
verbatim from
[GoogleCloudPlatform/knowledge-catalog](https://github.com/GoogleCloudPlatform/knowledge-catalog),
file `okf/SPEC.md`, pinned at commit **`ee67a5ca27044ebe7c38385f5b6cffc2305a9c1a`** (2026-06-12),
fetched 2026-07-10 and verified byte-identical with `cmp` (15,046 bytes).

Upstream is licensed **Apache License 2.0** (`okf/LICENSE.md`). The specification text is
**unmodified** — nothing was adapted, reformatted, or rewritten. Only this skill's tooling
(`scripts/`, `tests/`) is original work.

## Staleness

OKF v0.1 is a **Draft**. Upstream will move, and the failure is quiet: this skill would keep
validating against a specification the world has moved past. There is deliberately **no network
check** in the validator — it stays offline and deterministic.

Re-check upstream before relying on a conformance result for a new bundle:

    curl -sL "https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/SPEC.md" \
      | cmp - references/okf-0.1.md && echo "still current" || echo "UPSTREAM MOVED"

## Apache License 2.0 — NOTICE

Copyright Google LLC. Licensed under the Apache License, Version 2.0 (the "License"); you may not
use this file except in compliance with the License. You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied. See the License for the specific language governing permissions and limitations under the
License.
