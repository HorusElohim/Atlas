# Token-efficient Rust failure triage

Use this reference when the user wants minimal tool/output while diagnosing Rust tests.

1. Run the exact reported test command first; preserve suite setup and concurrency.
2. Bound output to the failing test, relevant source range, recent commit context, and final result.
3. An isolated rerun that passes means only “not reproduced in isolation.” Re-run the original suite before calling a failure flaky.
4. For an assertion mismatch, trace the producer and recent commits. Check implicit side effects and deterministic ordering before changing the expected value.
5. If the behavior is intentional and only the assertion is stale, update the smallest focused test; run the focused test plus package fmt/clippy.
6. Final response: root cause, file/line, verification, push/commit status, and any broader checks skipped.
