## Executor and tester repair loop

Cycle policy:

1. Executor implements change + minimal focused check.
2. Tester independently validates.
3. Production failures go back to executor.
4. Test/fixture failures can be repaired by tester.
5. Stop or escalate after two loops unless materially new evidence appears.
