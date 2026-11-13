# Validation record — Gemma 4 Developer Agent submission

Run: 14 Nov 2026 ~01:30 WIB, VM (no GPU), by the build agent.
Script: `python3 validate.py` (+ manual ADK check in `/tmp/venv-adk`).

## PASSED (both variants, 31b + e4b)

- All YAML files parse (custom loader resolving `!include` relative to the
  including file). One real bug caught and fixed during validation: the
  sub-agent's `!include` paths were relative to the variant root instead of
  `sub_agents/` (`prompts/analyzer.md` → `../prompts/analyzer.md`,
  `configs/sampling.yaml` → `../configs/sampling.yaml`).
- `agent.yaml`: model is an official checkpoint (`gemma-4-31b-it-qat-w4a16-ct`
  / `gemma-4-e4b-it-qat-w4a16-ct`); no `adapter` field (config-only, no LoRA);
  tools are exactly the 9 fixed harness tools + `agent_tool` (10 YAML entries);
  system prompt resolves via `!include` (2,755 chars); sampling config
  resolves (temperature 0.2, thinking_budget 4096 / 6144, include_thoughts true).
- Sub-agent `code_analyzer`: model identical to parent (single-model rule);
  read-only (no `edit_file` / `run_command`).
- `eval_config.yaml`: 5 min/task × 120 tasks = 600 min ≤ 720 min (12 h);
  max_tool_calls 24 ≤ community budget-fit 28.
- Skill `test_verifier`: SKILL.md present, script executable, no TODO/FIXME
  placeholders in prompts.
- Zips: `dist/submission-31b.zip` (4,888 bytes), `dist/submission-e4b.zip`
  (4,973 bytes); `agent.yaml` at zip root; 8 entries each; integrity OK;
  no path traversal, no symlinks, only `.yaml`/`.md`/`.sh` extensions;
  far below the 3 GiB limit.

## ADK load check (google-adk, installed in /tmp/venv-adk)

- `google.adk.agents.config_agent_utils.from_config` loads both variants and
  both sub-agents correctly for name / model / instruction /
  `generate_content_config` (temperature 0.2, top_p 0.95, max_output_tokens
  16384, thinking_config incl. budget) — verified with the tools section
  stripped out.
- Full `from_config` (with tools) FAILS in stock ADK with a pydantic
  ValidationError: the 9 harness tools (`run_command`, `read_file`, …) are
  bare-name strings that stock ADK cannot resolve to ToolConfig, and
  `agent_tool` is not a stock ADK tool shape. **This is expected, not a defect:**
  the official `sample_submission` uses exactly this format — the Kaggle
  harness resolves those tools itself. No stock-ADK run can validate them.

## NOT validated locally (honest gaps)

- No end-to-end evaluation run: needs the Kaggle notebook (GPU L4x4),
  the vLLM server, and the hidden dev dataset (129 public tasks:
  fastapi / rich / requests / httpx; full set 22.42 GB, accessible only after
  accepting the competition rules on Kaggle).
- No LoRA adapter: no GPU on this VM, so no fine-tuning was attempted.
- The Kaggle notebook source code cells could not be extracted via text
  fetch (Kaggle pages render only metadata/TOC); the package follows the
  `sample_submission` structure as documented in the task brief, which was
  verified against the official overview page and the walkthrough notebook
  (public score 0.15, best V8).
- Final Kaggle-side acceptance (zip upload, harness validation, leaderboard
  score) can only happen from the user's Kaggle account after rule acceptance.
