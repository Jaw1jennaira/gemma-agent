#!/usr/bin/env bash
# Run the test file most relevant to a fix. Usage:
#   run_relevant_tests.sh <test-path> [extra pytest args...]
# Exits with pytest's exit code. Prints only the last 60 lines of output
# (harness truncates command output at 5,000 chars anyway).
set -u
TEST_PATH="${1:?usage: run_relevant_tests.sh <test-path> [pytest args...]}"
shift || true
python -m pytest -x -q "$TEST_PATH" "$@" 2>&1 | tail -n 60
