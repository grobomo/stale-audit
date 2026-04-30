# stale-audit

Interactive staleness scanner and archive tool for a directory of git projects.

Scans repos, scores them by staleness (last commit age, missing config, empty `.git`, no remote), and presents a checkbox UI to select repos for archiving.

## Usage

```bash
python stale-audit.py                      # Interactive mode
python stale-audit.py --summary            # Summary only, no interaction
python stale-audit.py --dry-run            # Preview what would be archived
python stale-audit.py --json               # Machine-readable JSON output
python stale-audit.py --archive a b c      # Archive named repos (add --yes to skip prompt)
python stale-audit.py --dir /path/to/root  # Override projects directory
```

### Headless mode (for CI or Claude Code)

```bash
# Get JSON, pipe to jq or another tool
python stale-audit.py --json | jq '.[] | select(.score >= 40)'

# Archive specific repos without interaction
python stale-audit.py --archive old-project dead-repo --yes

# Preview archive without moving
python stale-audit.py --archive old-project --dry-run --yes
```

## Staleness Scoring

| Signal | Points |
|--------|--------|
| No commits | +50 |
| Empty `.git` dir | +40 |
| Last commit >6 months | +30 |
| Last commit >3 months | +20 |
| Last commit >2 months | +15 |
| Last commit >1 month | +10 |
| No remote | +10 |
| No `publish.json` | +3 |
| No `secret-scan.yml` | +2 |

**Labels:** DEAD (70+), STALE (40+), AGING (20+), QUIET (10+), ACTIVE (<10)

## Interactive Controls

| Key | Action |
|-----|--------|
| Arrow up/down | Move cursor |
| Space | Toggle selection |
| A | Toggle all STALE+ repos |
| Enter | Confirm selection |
| Q / Esc | Cancel |

DEAD repos are pre-selected. After confirming, you get a final `[y/N]` prompt before anything moves.

## Dependency Detection

Before scoring, the tool scans each repo's key files (CLAUDE.md, README.md, scripts, configs) for references to sibling project names. If project A references project B, B is marked as a dependency.

Repos depended on by active projects get their score **zeroed** and tagged `DEP: needed by X, Y`. This prevents archiving reference repos, shared libraries, or infrastructure projects that other active projects rely on.

## How It Works

1. Auto-detects group directories (any `_`-prefixed folder like `_grobomo/`, `_tmemu/`)
2. Scans each subfolder for `.git`
3. Detects dependencies between projects (grep-based, no LLM)
4. Scores and sorts by staleness (most stale first, dependencies protected)
5. Prints color-coded summary
6. Opens interactive selector
7. Moves selected repos to `Archive/`

## Environment

Set `PROJECTS_DIR` to override the default scan root (`~/Documents/ProjectsCL1`).

## License

MIT
