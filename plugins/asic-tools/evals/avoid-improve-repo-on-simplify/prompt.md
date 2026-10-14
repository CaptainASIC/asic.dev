---
description: improve-repo must not fire on a local simplify request
tags: [avoid, prp-lifecycle]
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
---

Simplify this function I just changed — it has three nested loops and duplicated branches:

```python
def matching_pairs(groups, target):
    result = []
    for group in groups:
        for a in group:
            for b in group:
                if a != b:
                    if a + b == target:
                        result.append((a, b))
                    else:
                        if a + b == target:
                            result.append((a, b))
    return result
```
