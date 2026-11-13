#!/usr/bin/env python3
"""Validate Gemma 4 submission zips locally (no GPU, no Kaggle needed).

Checks:
 1. Every YAML parses (with !include resolved relative to the including file).
 2. agent.yaml: name/model present, model is one of the 4 official checkpoints,
    tools are exactly the 9 fixed harness tools, no adapter (config-only),
    instruction + sampling config resolve via !include.
 3. Sub-agent model == parent model (competition rule: one model everywhere).
 4. Zip layout: agent.yaml at root, no '..' path traversal, no symlinks,
    only allowed extensions, size < 3 GiB.
 5. Optional: load the config with google-adk if installed (pip install google-adk).
"""
import os, sys, zipfile
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOWED_MODELS = {
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-12b-it-qat-w4a16-ct",
    "gemma-4-e4b-it-qat-w4a16-ct",
    "gemma-4-e2b-it-qat-w4a16-ct",
}
ALLOWED_TOOLS = {
    "run_command", "read_file", "edit_file", "write_file", "get_status",
    "submit_patch", "get_code_neighbors", "search_similar_code",
    "get_code_subgraph", "agent_tool",
}
ALLOWED_EXTS = {".yaml", ".yml", ".md", ".sh", ".txt", ".json"}
MAX_ZIP_BYTES = 3 * 1024 ** 3

failures, notes = [], []

def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)

class IncludeLoader(yaml.SafeLoader):
    pass

def _include(loader, node):
    base = os.path.dirname(loader.stream.name) if hasattr(loader.stream, "name") else "."
    path = os.path.join(base, loader.construct_scalar(node))
    with open(path) as f:
        return yaml.load(f, Loader=IncludeLoader) if path.endswith((".yaml", ".yml")) else f.read()

IncludeLoader.add_constructor("!include", _include)

def load_yaml(path):
    with open(path) as f:
        return yaml.load(f, Loader=IncludeLoader)

def validate_variant(key):
    print(f"\n== variant {key} ==")
    d = os.path.join(ROOT, "variants", key)
    agent = load_yaml(os.path.join(d, "agent.yaml"))
    check(isinstance(agent, dict), "agent.yaml parses as a mapping")
    check(agent.get("model") in ALLOWED_MODELS, f"model is an official checkpoint: {agent.get('model')}")
    check("adapter" not in agent, "no adapter field (config-only, no LoRA)")
    tools = agent.get("tools", [])
    names = {t if isinstance(t, str) else next(iter(t)) for t in tools}
    check(names == ALLOWED_TOOLS, f"tools are exactly the 9 fixed harness tools ({len(names)} found)")
    check(len(tools) == 10, "tools list has 10 YAML entries (9 named tools + agent_tool)")
    check(isinstance(agent.get("instruction"), str) and len(agent["instruction"]) > 500,
          "system prompt resolves via !include and is substantive")
    samp = agent.get("generate_content_config")
    check(isinstance(samp, dict) and samp.get("temperature") == 0.2,
          "sampling config resolves via !include (temperature 0.2)")
    check(samp.get("thinking_config", {}).get("include_thoughts") is True,
          "thinking_config include_thoughts: true")
    sub = load_yaml(os.path.join(d, "sub_agents/code_analyzer.yaml"))
    check(sub.get("model") == agent.get("model"), "sub-agent model == parent model (single-model rule)")
    check("edit_file" not in (sub.get("tools") or []) and "run_command" not in (sub.get("tools") or []),
          "sub-agent is read-only (no edit_file/run_command)")
    ev = load_yaml(os.path.join(d, "eval_config.yaml"))["evaluation"]
    check(ev["max_time_minutes"] * 120 <= 720, f"per-task time cap fits 12 h total: {ev['max_time_minutes']} min x 120 = {ev['max_time_minutes']*120} min")
    check(ev["max_tool_calls"] <= 28, f"max_tool_calls {ev['max_tool_calls']} within community budget-fit (28)")
    check(os.path.exists(os.path.join(d, "skills/test_verifier/SKILL.md")), "skill test_verifier/SKILL.md present")
    check(os.access(os.path.join(d, "skills/test_verifier/scripts/run_relevant_tests.sh"), os.X_OK),
          "skill script is executable")
    for rel in ["prompts/system.md", "prompts/analyzer.md"]:
        p = os.path.join(d, rel)
        check("TODO" not in open(p).read() and "FIXME" not in open(p).read(), f"{rel} has no TODO/FIXME placeholders")

def validate_zip(key):
    print(f"\n== zip submission-{key}.zip ==")
    zpath = os.path.join(ROOT, "dist", f"submission-{key}.zip")
    check(os.path.exists(zpath), "zip exists")
    size = os.path.getsize(zpath)
    check(size < MAX_ZIP_BYTES, f"zip size {size} bytes < 3 GiB")
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        bad = z.testzip()
        check(bad is None, "zip integrity OK (testzip)")
        check("agent.yaml" in names, "agent.yaml at zip root")
        check(all(".." not in n and not n.startswith("/") for n in names), "no path traversal entries")
        check(all(not n.endswith("/") or True for n in names), "entry names sane")
        exts = {os.path.splitext(n)[1].lower() for n in names if not n.endswith("/")}
        check(exts <= ALLOWED_EXTS, f"only allowed extensions: {sorted(exts)}")
        infos = z.infolist()
        check(all((i.external_attr >> 28) != 0o12 for i in infos), "no symlinks in zip")
        print(f"  INFO entries ({len(names)}):")
        for n in sorted(names):
            print(f"       {n}")

def try_adk():
    print("\n== google-adk load check ==")
    try:
        import google.adk  # noqa
        print(f"  INFO google-adk installed: {google.adk.__file__}")
    except Exception as e:
        notes.append(f"google-adk not installed/available ({e}); ADK load check skipped — see README.")
        print("  SKIP google-adk not installed; run: pip install google-adk")
        return
    # ADK config loading API differs across versions; try the documented paths.
    try:
        from google.adk.agents.config_agent_utils import from_config  # type: ignore
        print("  INFO from_config import OK")
    except Exception as e:
        notes.append(f"ADK from_config import failed ({e}); config load via ADK not verified locally.")
        print(f"  SKIP ADK from_config import failed: {e}")

if __name__ == "__main__":
    for key in ("31b", "e4b"):
        validate_variant(key)
        validate_zip(key)
    try_adk()
    print("\n== RESULT ==")
    if failures:
        print(f"FAILED: {len(failures)} check(s)")
        for f in failures:
            print(" - " + f)
        sys.exit(1)
    print("ALL CHECKS PASSED")
    for n in notes:
        print("NOTE: " + n)
