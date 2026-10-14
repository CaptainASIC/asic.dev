# Root-cause tracing

Bugs surface deep in the call stack: a file written to the wrong directory, a query sent to the
wrong database. Fixing the line where the error appears treats the symptom. Trace backward to the
original trigger and fix it there.

## Trace backward

1. **Symptom** — the error, and where it appears.
2. **Immediate cause** — the line that directly produces it.
3. **Caller** — what called that line, and with which values?
4. **Keep going up** until you reach the point where the bad value was created.
5. **Fix at the source**, then consider guarding the layers in between (`hardening.md`).

Upstream's worked case: `git init` ran inside the source tree because an empty working-directory
argument fell back to the process's current directory. The empty value came from a test fixture
read before setup had assigned it. The fix went into the fixture, which now fails when read too
early, not into the `git init` call.

## When reading is not enough

Capture the stack right before the suspicious operation, together with its inputs. Python:

```python
import os  # [DEBUG-a4f2]
import sys  # [DEBUG-a4f2]
import traceback  # [DEBUG-a4f2]

print(f"[DEBUG-a4f2] directory={directory!r} cwd={os.getcwd()!r}", file=sys.stderr)
traceback.print_stack(file=sys.stderr)  # [DEBUG-a4f2]
```

Write to stderr: log configuration can swallow `logging` output in tests. Run with
`uv run pytest -s` so pytest does not capture it. Tag every probe line with the session's debug
prefix — imports and the `print_stack` call included, not only the print — so Phase 7 can remove
every line with one grep.

## Bisect a regression

With a known-good commit, a known-bad commit and the Phase 1 loop saved as a script:

```bash
git bisect start <bad> <good>
git bisect run /absolute/path/to/loop.sh
git bisect reset
```

The script's exit code is the verdict: `0` is good; `1`–`127` is bad, except `125`, which skips a
commit that cannot be tested; any other code aborts the bisect (`git help bisect`, "Bisect run").
So the script must exit `1` only when the symptom is observed, `0` on a clean pass, and `125` for
pytest exit codes 2, 4 or 5 (interrupted, test id not found, nothing collected) or any setup
failure — otherwise a commit from before the test existed counts as bad and bisect lands wrong.
Keep the script in the scratchpad, outside the work tree: bisect checks out each commit in turn,
and a script inside the tree can change or disappear underneath it.

## Find a polluting test

Something appears during the suite and no single test owns it.

**On-disk pollution** (a stray file or directory): run the test files one at a time and stop at
the first one that produces it. This loop finds on-disk pollution only:

```bash
POLLUTION=path/that/appears
found=
while IFS= read -r f; do
  uv run pytest -q "$f" >/dev/null 2>&1
  if [ -e "$POLLUTION" ]; then echo "polluter: $f"; found=1; break; fi
done < <(git ls-files 'tests/*test_*.py')
[ -n "$found" ] || echo "no polluter found"
```

Clear the pollution before you start, or every file looks guilty. A single `*` in a git pathspec
matches across directories, so nested test files are included. Upstream ships an npm-specific
script for this technique; the loop above is the same technique for pytest.

**In-memory state** (a module-level list, a cache, a patched global — a victim that passes alone
and fails in the suite): nothing appears on disk, so drive the search from the victim. Run each
candidate file together with the victim, in that order, and stop at the first pairing that fails:

```bash
VICTIM=tests/test_victim.py::test_x
found=
while IFS= read -r f; do
  if ! uv run pytest -q "$f" "$VICTIM" >/dev/null 2>&1; then
    echo "polluter: $f"; found=1; break
  fi
done < <(git ls-files 'tests/*test_*.py')
[ -n "$found" ] || echo "no polluter found"
```

Confirm first that the victim passes alone, or every file looks guilty. If only the victim's own
file pollutes it, repeat the search over that file's test ids.
