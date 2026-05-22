---
name: speckit-v-model-impact-analysis
description: Run deterministic impact analysis to identify all V-Model artifacts affected
  by a change to one or more IDs.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: v-model:commands/impact-analysis.md
---

## User Input

```text
$ARGUMENTS
```

## Goal

Run **deterministic impact analysis** on V-Model artifacts to identify the blast radius of a change. This is a **script-only command** — no AI generation is needed. The script scans all markdown files in the V-Model directory, builds an ID dependency graph, and traverses it from the specified changed IDs to produce an impact report.

## How to Use

This command is invoked directly via the script, not through AI generation:

### Bash
```bash
# Downward traversal (default): what depends on REQ-001?
.specify/scripts/bash/impact-analysis.sh --downward REQ-001 specs/<feature>/v-model

# Upward traversal: what does MOD-003 depend on?
.specify/scripts/bash/impact-analysis.sh --upward MOD-003 specs/<feature>/v-model

# Full traversal: complete blast radius of SYS-002
.specify/scripts/bash/impact-analysis.sh --full SYS-002 specs/<feature>/v-model

# JSON output to stdout
.specify/scripts/bash/impact-analysis.sh --json --downward REQ-001 REQ-002 specs/<feature>/v-model

# Custom output path
.specify/scripts/bash/impact-analysis.sh --output /tmp/report.md REQ-001 specs/<feature>/v-model
```

### PowerShell
```powershell
# Downward traversal (default)
.specify/scripts/powershell/impact-analysis.ps1 -Downward -Ids REQ-001 -VModelDir specs/<feature>/v-model

# Upward traversal
.specify/scripts/powershell/impact-analysis.ps1 -Upward -Ids MOD-003 -VModelDir specs/<feature>/v-model

# Full traversal with JSON output
.specify/scripts/powershell/impact-analysis.ps1 -Full -Json -Ids SYS-002 -VModelDir specs/<feature>/v-model
```

## Output

The script produces an **Impact Analysis Report** containing:

1. **Changed IDs** — The IDs specified by the user with their V-Model level
2. **Suspect Artifacts** — All affected IDs organized by V-Model level
3. **Blast Radius** — Statistics showing the count of affected artifacts per level
4. **Re-validation Order** — Ordered list of artifacts that should be re-validated

### Traversal Modes

| Mode | Flag | Description |
|------|------|-------------|
| Downward | `--downward` (default) | Traces from changed IDs to all downstream dependents |
| Upward | `--upward` | Traces from changed IDs to all upstream parents |
| Full | `--full` | Both directions, with upstream/downstream separation |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Analysis completed successfully |
| 1 | Error (invalid args, no artifacts, no valid IDs) |

## Quality Criteria

- The script is **deterministic**: same inputs always produce the same output
- The script is **read-only**: no existing V-Model artifacts are modified
- The script uses **no external tooling** beyond standard Bash/PowerShell utilities
- The script completes within **10 seconds** for projects with up to 20 files and 500 IDs
- Bash and PowerShell produce **identical JSON structure** and exit codes