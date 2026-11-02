# MEL-005 plan

Docs only; no helper code changes. Add `references/unattended.md` (E1) and a "Proof and review hygiene" section in
`references/delivery.md` (E2), with one-line pointers from `SKILL.md` and `references/capacity.md` (E3).
Every fact is taken from the relayed lessons and checked against the reference implementation
a private project's `.claude/codex-queue/run_queue.py` (CREATE_NO_WINDOW 0x08000000, newest
`AppData/Local/OpenAI/Codex/bin/*/codex.exe`, worktree + branch per spec cut from master, done/<name>.json with
`reviewed_by_claude`/`merged` false, short `status` record on early failure, waits while scan locks exist).
Statements are worded as lessons with their date and source, not as universal guarantees. Proof: `python -B scripts/validate.py` (links, metadata) and the full test suite
unchanged. Review rules stay consistent with delivery.md/standards.md: a cloud reviewer counts only as the other native
provider of each builder (any native for backend-built work), and fix commits it pushes are new authorship that
needs their own independent review. `git apply --3way` is documented as able to leave conflict markers (check
exit code and `git status`, resolve, review the diff, commit), and a done file means attempted, not delivered.
Review: Codex plan check, then Codex final inspection of the diff; PR stacked on #4.
