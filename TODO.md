# stale-audit TODO

## Active
- [x] T001: Create stale-audit.py — scan, score, interactive checkbox UI, archive (merged to main)
- [x] T002: Add publish.json, secret-scan.yml, .gitignore, README (merged to main)
- [x] T003: Push to grobomo/stale-audit (https://github.com/grobomo/stale-audit)
- [x] T004: Verify end-to-end — 64 repos, scoring categories confirmed
- [x] T005: Add --json and --archive flags for headless/CI mode (pushed)
- [x] T006: Dependency detection — grep key files for sibling refs, zero score for depended-on repos, 44 protected, 6 candidates remain
- [x] T007: Update README with --json, --archive, dependency detection docs (PR #2)
- [x] T008: Add MIT LICENSE file (PR #1)
- [x] T009: Push final state to GitHub — sync all merged PRs to remote (PR #3)
- [x] T010: Add SESSION_STATE.md to .gitignore — context-reset artifact shouldn't be tracked (PR #5)
- [ ] T011: Create Claude Code skill (SKILL.md) for invoking stale-audit from any session
