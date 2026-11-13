#!/usr/bin/env python3
"""Generate the two Gemma 4 Developer Agent submission variants (31B + E4B)
from shared templates, then build + validate submission zips.

Config-only submission (no LoRA adapter). Structure follows the official
sample_submission as documented in the Kaggle starter notebook
(Ryan Holbrook, 'Getting Started - Gemma 4 Developer Agent') and the
public walkthrough notebook (zhukovoleksiy, best public score 0.15).
"""
import os, sys, json, zipfile, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
VARIANTS = {
    "31b": {
        "model": "gemma-4-31b-it-qat-w4a16-ct",
        "name": "gemma_swe_agent_31b",
        "thinking_budget": 4096,
        "note": "Main track, highest capability. Default / first Final Submission slot.",
    },
    "e4b": {
        "model": "gemma-4-e4b-it-qat-w4a16-ct",
        "name": "gemma_swe_agent_e4b",
        "thinking_budget": 6144,
        "note": "Faster + eligible for the $10,000 Small Model Development bonus "
                 "(highest-ranked main-track submission using Gemma E2B/E4B). "
                 "Higher thinking budget compensates for the smaller model; "
                 "its lower latency keeps it inside the per-task time budget.",
    },
}

SYSTEM_MD = """You are an autonomous software engineer fixing ONE issue in the Python repository at /workspace. No one will answer questions — keep working with your tools until the fix is in place, then call submit_patch().

## WORKFLOW

1. **Orient (cheap first).** Call get_status() to see the issue text and the repo state. Read the issue description carefully — it names the failing behaviour and often the test that must pass.
2. **Locate.** Use get_code_subgraph, search_similar_code and get_code_neighbors to find the relevant module(s). Read the suspect code with read_file (max 150 lines per call — read in slices). Read the related TEST file(s) FIRST to learn the expected behaviour; never edit tests.
3. **Reproduce (if cheap).** Run the failing test or a minimal repro with run_command. One short command. If reproduction is expensive, skip it and reason from the test.
4. **Fix minimally.** Change only the code needed to fix the issue. Do not refactor, rename, or "improve" unrelated code. Keep the diff small — every extra line is a chance to break a hidden test.
5. **Verify.** Run the related test file(s) with run_command (`python -m pytest -x -q <test-path>`), or via the test_verifier skill. If the fix breaks other tests in the same module, adjust. Do NOT run the whole test suite — it wastes the time budget.
6. **Submit.** Call submit_patch() as soon as the related tests pass. Do not keep polishing.

## RULES

- You are OFFLINE. Do not install packages, do not access the network, do not pip install anything.
- NEVER edit test files, pytest.ini, conftest.py, or any file under tests/ that is a test. Only edit source code.
- run_command has a 300-second timeout; command output is truncated to 5,000 characters. Prefer short, targeted commands.
- read_file returns at most 150 lines per call. Use slices/offsets for longer files.
- get_status() and submit_patch() are FREE — they do not count against your tool-call budget. Use get_status() whenever you are unsure what remains.
- BUDGET: you have about 5 minutes and ~24 tool calls per task. If you are halfway through your budget and have no fix yet, stop exploring, write the smallest plausible fix, run the ONE most relevant test, then submit_patch().
- If a test fails for an unrelated, pre-existing reason, note it and do not chase it — fix only the reported issue.
- Never leave the repo in a broken state: if an edit makes things worse, revert it with edit_file before submitting.
- When choosing between two fixes, pick the one that matches the existing code style and the test's expectations.
- If you cannot reproduce the issue and cannot find the fault after a focused search, make the smallest change consistent with the issue text and submit — an attempted patch beats no patch.
"""

ANALYZER_MD = """You are a read-only code-analysis sub-agent. Given a file path, symbol, or question, inspect the Python repository at /workspace and return a concise, factual report: what the code does, the relevant functions/classes with their line ranges, how data flows, and where the reported issue most likely lives.

Use read_file, get_code_neighbors, search_similar_code, and get_code_subgraph. Do NOT edit files, do NOT run commands, do NOT submit anything — analysis only. Keep the report under ~800 words and end with the 1–3 most likely root-cause locations, ranked.
"""

SKILL_MD = """# test_verifier

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
"""

RUN_TESTS_SH = """#!/usr/bin/env bash
# Run the test file most relevant to a fix. Usage:
#   run_relevant_tests.sh <test-path> [extra pytest args...]
# Exits with pytest's exit code. Prints only the last 60 lines of output
# (harness truncates command output at 5,000 chars anyway).
set -u
TEST_PATH="${1:?usage: run_relevant_tests.sh <test-path> [pytest args...]}"
shift || true
python -m pytest -x -q "$TEST_PATH" "$@" 2>&1 | tail -n 60
"""

def agent_yaml(v):
    return f"""# Gemma 4 Developer Agent Competition 2026 — {v['name']}
# {v['note']}
# Model: {v['model']} (exactly ONE model; every agent + sub-agent uses it)
# Config-only submission: no LoRA adapter (fine-tuning needs a GPU).
name: {v['name']}
model: {v['model']}
description: Autonomous SWE agent for the Gemma 4 Developer Agent Competition — config-only, {v['model']}.
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
  - agent_tool:
      config_path: sub_agents/code_analyzer.yaml
      skip_summarization: true
generate_content_config: !include configs/sampling.yaml
"""

def sampling_yaml(v):
    return f"""# Sampling config — {v['model']}
# Low temperature for deterministic, careful edits; thinking budget kept
# inside the per-task time budget (see eval_config.yaml).
temperature: 0.2
top_p: 0.95
max_output_tokens: 16384
thinking_config:
  thinking_budget: {v['thinking_budget']}
  include_thoughts: true
"""

def analyzer_yaml(v):
    return f"""# Read-only code-analysis sub-agent. Model MUST match the parent agent exactly.
name: code_analyzer
model: {v['model']}
description: Read-only code analysis sub-agent — locates relevant code and likely root causes for the main agent.
instruction: !include ../prompts/analyzer.md
tools:
  - read_file
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include ../configs/sampling.yaml
"""

# Budget math (documented in README too):
# 12 h total for ~120 tasks = 6 min/task gross. Setup + vLLM server start
# consume part of the 12 h, so the per-task cap is set to 5 min and
# 24 tool calls (~1 call per 12 s). get_status()/submit_patch() are free.
# max_turns 40 gives headroom above the 24-call cap for short turns.
# timeout_seconds 300 matches the run_command limit.
EVAL_CONFIG = """# Per-task budget — fits the 12-hour total for ~120 tasks.
# 12 h / 120 tasks = 6 min/task gross; setup + vLLM start take part of it,
# so the cap is 5 min/task and 24 tool calls. get_status() and submit_patch()
# are free (not counted). Values are caps, not targets: most tasks finish
# well under them. (Community "Budget-Fit" note: 28 calls / 8 min per task
# would exceed 12 h if every task used the full budget, so we stay below it.)
evaluation:
  timeout_seconds: 300
  max_tool_calls: 24
  max_time_minutes: 5
  max_turns: 40
"""

def build_variant(key, v):
    d = os.path.join(ROOT, "variants", key)
    files = {
        "agent.yaml": agent_yaml(v),
        "configs/sampling.yaml": sampling_yaml(v),
        "prompts/system.md": SYSTEM_MD,
        "prompts/analyzer.md": ANALYZER_MD,
        "sub_agents/code_analyzer.yaml": analyzer_yaml(v),
        "eval_config.yaml": EVAL_CONFIG,
        "skills/test_verifier/SKILL.md": SKILL_MD,
        "skills/test_verifier/scripts/run_relevant_tests.sh": RUN_TESTS_SH,
    }
    for rel, content in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
    os.chmod(os.path.join(d, "skills/test_verifier/scripts/run_relevant_tests.sh"), 0o755)
    return files

def build_zip(key):
    src = os.path.join(ROOT, "variants", key)
    out = os.path.join(ROOT, "dist", f"submission-{key}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(src):
            for fn in sorted(filenames):
                full = os.path.join(dirpath, fn)
                arc = os.path.relpath(full, src)
                z.write(full, arc)
    return out

if __name__ == "__main__":
    for key, v in VARIANTS.items():
        files = build_variant(key, v)
        print(f"{key}: wrote {len(files)} files -> variants/{key}/")
        z = build_zip(key)
        print(f"{key}: {z} ({os.path.getsize(z)} bytes)")
