# Agent Smith policy reference

## Routing signals

Prefer `direct` when the task is small, coupled, already understood, or has one natural edit owner.

Prefer `structured` when discovery can run independently, a specialist review matters, or an executor/tester loop reduces uncertainty without creating writer contention.

Prefer `parallel` only when work packages are independent, interfaces are stable, ownership does not overlap, and integration plus verification remains cheaper than sequential work.

## Ownership rules

- Assign one writer to a file or shared generated state at a time.
- Parallel read-only work is safe when questions are distinct.
- Use isolated worktrees for parallel writers; name the integration owner.
- Never let a worker commit, push, deploy, message externally, rotate credentials, or perform destructive remediation unless the user explicitly authorized that exact boundary and the primary thread retains custody.
- Stop expanding the topology when another agent would not materially improve confidence or elapsed time.

## Bounded packet example

```text
Outcome: identify why Windows startup fails.
Done when: return the first failing boundary with source evidence and a focused reproduction.
Boundaries: read-only; inspect startup and config-loading paths only.
Authoritative context: failure log and current branch.
Non-goals: no fixes, dependency upgrades, or broad cleanup.
Required handoff: files/lines, reproduction command/result, uncertainty, recommended next check.
```

## Verification ladder

1. Syntax, schema, or import validation.
2. Focused behavioral regression.
3. A realistic clean-project or clean-environment smoke test.
4. Broader affected suite.
5. Independent review for consequential changes.

Use only the levels needed to resolve material uncertainty.
