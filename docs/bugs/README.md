# Bug backlog (Phase 1)

Use this folder for **Critical** and **High** issues that block or risk release. File naming: `BUG-{N}.md` (see `.cursor/rules/quality-analyst.mdc` for the template).

**Process**

1. Create `BUG-{N}.md` when an issue is confirmed (not for every draft idea).
2. Link to the regression test or the PR that fixes it.
3. Set **Status** to `Verified` only after the test passes in CI.

When the backlog is empty for a release, note that in `docs/qa/phase-validation-sign-off.md`.
