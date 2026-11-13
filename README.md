# gemma-agent — Google Gemma 4 Developer Agent Competition 2026 (Kaggle)

Config-only ADK agent submission for the [Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent/overview)
(host: Google DeepMind, Kaggle Featured). Total prize $110,000: main track $65,000
(1st $37,000 / 2nd $18,000 / 3rd $10,000, decided by the Private Leaderboard) +
$10,000 Small Model Development bonus + Paper Track $35,000 (closed 12 Nov 2026 — not touched).

**No LoRA adapter.** Fine-tuning needs a GPU; this VM has none. Config-only
submissions are valid — the sample submission ships the same way.

## Variants (2 Final Submission slots)

| Slot | Model | Zip | Notes |
|---|---|---|---|
| 1 (default) | `gemma-4-31b-it-qat-w4a16-ct` | `dist/submission-31b.zip` | Highest capability; best expected score on the main track. |
| 2 | `gemma-4-e4b-it-qat-w4a16-ct` | `dist/submission-e4b.zip` | Faster; eligible for the **$10,000 Small Model bonus** (highest-ranked main-track submission using Gemma E2B/E4B). Thinking budget raised to 6144 to compensate for the smaller model. |

Both variants use exactly ONE model everywhere (main agent + sub-agent) — the
competition forbids mixing models.

## Package contents (identical layout in both zips)

```
submission-<variant>.zip
├── agent.yaml                        # ADK config at zip root (required)
├── configs/sampling.yaml             # temperature 0.2, top_p 0.95, max_output_tokens 16384, thinking on
├── prompts/system.md                 # main system prompt (workflow + rules)
├── prompts/analyzer.md               # sub-agent prompt
├── sub_agents/code_analyzer.yaml     # read-only code-analysis sub-agent
├── eval_config.yaml                  # per-task budget (see below)
└── skills/test_verifier/
    ├── SKILL.md
    └── scripts/run_relevant_tests.sh # runs the single most relevant test file
```

Tools are exactly the 9 fixed harness tools (`run_command`, `read_file`,
`edit_file`, `write_file`, `get_status`, `submit_patch`, `get_code_neighbors`,
`search_similar_code`, `get_code_subgraph`) plus the `agent_tool` sub-agent call —
no custom tools.

## Strategy (system prompt)

1. Orient with free `get_status()`; read the issue + related tests first.
2. Locate code via graph tools (`get_code_subgraph`, `search_similar_code`,
   `get_code_neighbors`); read in ≤150-line slices.
3. Reproduce cheaply if possible; otherwise reason from the test.
4. Minimal patch only — no refactoring, no test edits, never touch
   `tests/`/`pytest.ini`/`conftest.py`; offline, no installs.
5. Verify with the single most relevant test file (`test_verifier` skill).
6. `submit_patch()` as soon as related tests pass — no polishing.

## Per-task budget (eval_config.yaml)

12 hours total for ~120 hidden tasks ≈ 6 min/task gross. Setup + vLLM server
start consume part of the 12 h, so the cap is **5 min/task, 24 tool calls,
40 turns, 300 s command timeout** (120 × 5 min = 600 min, leaving ~2 h for
setup/server start). `get_status()`/`submit_patch()` are free. These are caps,
not targets — most tasks finish well under them. (A community "Budget-Fit" note
suggested 28 calls / 8 min per task, but 120 × 8 min = 960 min > 12 h if every
task used the full budget, so we stay below it.)

## Deadlines (user action required)

- **Accept rules + join/merge team by 25 Nov 2026 23:59 UTC (= 26 Nov 06:59 WIB)** —
  hard gate: without accepting the rules you cannot submit at all.
- **Final submission by 2 Dec 2026 23:59 UTC (= 3 Dec 06:59 WIB).**
- Max 2 Final Submissions per team, 1 submission/day. Solo allowed.

Submit via the user's Kaggle account: upload `dist/submission-31b.zip` (slot 1)
and `dist/submission-e4b.zip` (slot 2) as the two Final Submissions.

## Build & validate

```bash
python3 build_submission.py   # regenerate variants/ + dist/*.zip
python3 validate.py           # YAML parse (+!include), model/tool checks, zip checks
```

See [VALIDATION.md](VALIDATION.md) for the full validation record, including
what could NOT be validated locally.

## References

- Competition: https://www.kaggle.com/competitions/gemma-4-developer-agent/overview
- Starter notebook (Kaggle Staff Ryan Holbrook): https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent
- Public walkthrough + sample_submission dump (best public score 0.15): https://www.kaggle.com/code/zhukovoleksiy/gemma-4-walkthrough-findings-submission
- ADK config docs: https://adk.dev/agents/config/
