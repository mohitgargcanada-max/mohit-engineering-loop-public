# Mistakes

## 2026-10-22 - upstream review adapter compatibility
The installed development adapter passed a flag unsupported by the installed Claude
CLI. Read the actual CLI diagnostics/help, preserve read-only restrictions, and do
not infer compatibility from authentication alone. This project ships no such adapter.

## 2026-10-22 - recursive mock in a merge-readback test
The test captured subprocess.run after patching it, so its Git fallback called
the mock recursively. Capture the real callable before patching; mock only the
GitHub response and retain actual Git checks in the disposable fixture.

## 2026-10-22 - test fixture compared short and expanded Windows paths
Windows CI's temporary root used an 8.3 alias while the helper returned its resolved
long path. The checkout test called relative_to on different representations of the
same directory and failed before Git checkout. Resolve fixture roots at construction
so tests and production path binding compare the same canonical location.

## 2026-10-24 - commit claimed "ready" after the ready command failed (Claude)
`task_state.py ready ... | grep | tail -1 ; git commit -m "MEL-002 ready"` ran the commit although `ready`
refused ("Fresh other-provider inspection required"): the pipeline's exit status was `tail`'s, so the `&&`
chain never saw the failure, and commit 51322e9 states a status the helper had rejected. The refusal itself
was correct: passing B8 after recording the inspection cleared the review, by design. Do instead: pass every
criterion before recording the final inspection; run gating commands with `set -o pipefail` (or without a
pipe) and read the resulting status before writing it into a commit message. Corrected in the next commit.
