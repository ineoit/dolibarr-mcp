# Docs — specification, plan, TODO, backups, graft

## SPECIFICATION.md / PLAN.md / TODO.md

- `SPECIFICATION.md` is the single source of truth: numbered FR-x / NFR-x with acceptance criteria. Never
  build a feature not in the specification; when scope changes, update it in the same commit as the code
  and reference the FR number in the commit message.
- `PLAN.md` phases the FRs; append a short "Done" note per delivered item.
- `TODO.md` holds only steps currently in progress; purge when done (history lives in git and
  CHANGELOG.md). Anything not yet actionable goes to GitHub issues, not TODO.md.
- `backups/` holds local copies of the three files; keep them in sync after edits.

## Other docs

- `docs/` holds user/contributor guides (quickstart, configuration, development, api-reference);
  `docs/README.md` is the index.
- `graft/` is the repo context graph — run `graft map` for orientation, `graft ask "<question>"` for code
  context with exact file:line spans. After big code changes, refresh with `graft build`.

## Commits

- Work on a feature branch; `main` is protected by the pre-commit `no-commit-to-branch` hook.
- Factual commit messages; reference FR numbers and issue numbers when relevant.
- Documentation (spec, plan, TODO, docs) lands in commits too — never leave completed work uncommitted.

## Standing instructions (consignes)

- **"Noter" means writing it in `TODO.md` immediately**, not just in chat.
- **Self-green commits**: fix each problem in the commit that introduced it — never leave a known
  breakage for a later commit to repair.
- **CI-green is a completion condition**: a task is finished only when the GitHub `integration` workflow
  (`.github/workflows/integration.yml`) passes for the branch, in addition to the local suites. If CI is
  currently red, resolve that first with a dedicated agent before imposing the condition on new work.
- **Sub-agents load `ponytail` first**: spawn the child with only the skill load as its first turn, then
  send the task on the next turn so the skill stays cached.
- **Sub-issue agents push and verify CI**: after committing on the feature branch, the agent pushes the
  branch and watches the GitHub `integration` workflow run for its commit
  (`gh run list --repo <owner>/dolibarr-mcp --branch <branch>`, `gh run watch`); if CI fails because of
  its change, it fixes it within its own commit (amend/rebase its tip commit) and pushes again.
- **Multi-version CI**: the integration workflow runs a matrix over the pinned Dolibarr versions (21.0.0
  and 24.0.4) with a per-version cache key and one PHP install pinned to the highest version supported by
  the smallest Dolibarr (8.3); prefer running both versions on the same runner. Changes to the workflow
  are GitHub-side only — verify them through actual workflow runs.
