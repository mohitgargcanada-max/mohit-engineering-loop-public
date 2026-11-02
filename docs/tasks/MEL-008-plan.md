# MEL-008 plan

Docs only. Copy the five files from `~/.agents/skills/mohit-engineering-loop` into `skills/mohit-engineering-loop/` unchanged (the
Agentation section and visual-feedback.md are byte-identical on both hosts; Codex's 2026-10-29 edits exist only on the Codex host).
Record authorship with `init --adopt-unknown` (imported text written outside a task: Codex on 2026-10-29 for backends/unattended/
standards/version, an unrecorded session for the Agentation material); the scope and this plan are by the coordinator. Proof:
`python -B scripts/validate.py` and the full unittest suite. Review: Claude and Codex each inspect the import (unknown authorship needs
both); low notes may be listed, not rewritten here. Criteria J1-J3 gate readiness; merge and install are post-merge steps: merge on Mohit's go (given 2026-10-30), record merged, land the
state on main, install both hosts from the merged tree with a backup, then confirm both installed copies equal the repository.
