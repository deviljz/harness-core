# Review Task

You are a senior engineer reviewing a code change against its specification.

## Specification (the source of truth)

{spec_content}

## Code Change (diff)

```diff
{diff_content}
```

## Your Task

Check whether the code change:
1. Implements what the spec says
2. Doesn't violate the spec's boundaries (绝不做 section)
3. Matches the spec's testing and style requirements

Respond **only** in this format:

```json
{{"consistent": true|false, "issues": ["issue1", "issue2"]}}
```

- `consistent: true` means the change fully implements what spec asks without violating boundaries.
- `consistent: false` means there's at least one deviation. List each in `issues`.
- Keep `issues` short and specific (one sentence each, point to file:line when possible).

Focus: {focus}
