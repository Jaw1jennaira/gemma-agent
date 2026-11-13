# test_verifier

## When to use
After editing source code, before calling submit_patch(): run the test file(s) most relevant to the fix and confirm they pass. Never run the whole test suite — it wastes the per-task time budget.

## How
Run the bundled script with the single most relevant test path:

```
run_skill_script test_verifier scripts/run_relevant_tests.sh tests/test_<module>.py
```

The script runs `python -m pytest -x -q <test-path>` and prints the last 60 lines of output. A zero exit code plus a passing summary means the fix is verified for that module. If the test fails, read the failure output, adjust the fix, and re-run once. If it still fails after two attempts, submit the best patch anyway — do not burn the whole time budget on one test file.

## Rules
- Only test paths inside the repo; never pass absolute paths outside /workspace.
- Never edit test files; this skill only RUNS them.
- Keep each run to one test file (or one test node, e.g. `tests/test_x.py::TestY::test_z`).
