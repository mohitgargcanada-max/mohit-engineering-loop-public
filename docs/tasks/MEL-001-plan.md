# MEL-001 implementation plan

Build an original instruction skill plus a small Python stdlib state helper.
Preserve user requirements in A1-A7 (MEL-001.md). Quality/reliability constrain
cost, token and latency optimization. No upstream code, text, artwork or adapters
are redistributed. Chase AI is credited as inspiration; CRISP is optional.

The real coordinator selects agents/roles/models/stack with explicit constraints.
One canonical revisioned task file, immutable numbered handoffs, optimistic revision
checks, cooperative locks and atomic replacement manage continuity. Git fingerprints,
plan/proof/report hashes and other-provider inspection gate readiness; GitHub readback
verifies actual merge. Report provenance and acceptance truth are coordinator
attestations; this helper is not a security sandbox or autonomous agent runtime.

Proof: `python -B -m unittest discover -s tests -v`, `python -B scripts/validate.py`,
Git diff review and isolated CLI lifecycle smoke tests. Cover good and rejected
paths for concurrency, ownership, stale snapshots, pending transfers and readiness.
Install the single new skill for both hosts after tests; publish a draft PR.
Independent Claude review and merge are deferred by explicit user authorization.
