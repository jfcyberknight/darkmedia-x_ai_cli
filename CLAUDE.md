# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python CLI dashboard (`list_ai_clis.py`) for Windows that detects installed AI coding assistant CLIs (Claude Code, OpenCode, KiloCode, Mistral Vibe/CLI, Antigravity CLI), shows their versions, and lets the user launch one interactively from a menu. It also creates a desktop shortcut ("Mes CLI IA") on first run.

It also embeds a **local orchestrator agent** (menu option `[A]`). The user types a request in natural language; a **local LLM via Ollama** (no cloud, no subscription) then drives the installed CLIs as **headless tools** — it picks a CLI, crafts a precise sub-prompt, and (after the user confirms that specific call) runs the CLI non-interactively, captures its stdout, and loops: observe → decide next CLI → … → synthesize a final answer. The brain never opens an interactive CLI session (that would hand off control and lose the orchestration). A keyword-based single-step fallback kicks in if the Ollama server is unreachable. E.g. "crée-moi un VPS gratuit sur Google" → the brain delegates to `agy` headlessly.

Key design point: the value is the **brain staying in control across steps**, using CLIs as callable tools (like a function-calling agent), not just routing-and-launching. Each CLI call is gated by an explicit user confirmation before it runs (with action rights / auto-approval).

## Running

```bash
python list_ai_clis.py
```

There is no build step, package manager, dependency file, linter, or test suite in this repo — it's a single stdlib-only script. Requires Python 3.7+.

## Architecture

Everything lives in `list_ai_clis.py`, organized as:

- **`CLI_TOOLS`** — the list of dicts declaring which CLI tools to detect. Per entry: `key`, `name`, `command`, `desc`, `skills` (French description of strengths, fed to the LLM for tool selection), `headless` (argv template for a non-interactive call, with a `{prompt}` placeholder — e.g. `['-p', '{prompt}']` for agy/claude, `['run', '{prompt}']` for opencode/kilo), `auto_approve` (extra flags granting the tool action rights, e.g. `--dangerously-skip-permissions`), `model_flag` (how to force a model — `--model`, `-m`, or `None` if the CLI has no CLI model flag like vibe/mistral), and `default_model` (the cheapest model, applied when the user hasn't overridden it; `None` = the CLI's own default). To support a new tool, add an entry with all of these so the orchestrator can select **and** drive it.
- **Per-CLI model config** (`load_model_overrides`, `save_model_overrides`, `MODEL_CONFIG_PATH`, `list_cli_models`, `configure_models`) — the `[M]` menu. User model choices persist to `ai_cli_models.json` next to the script (gitignored). `scan_tools` resolves each tool's baseline `model` = override else `default_model`; `build_headless_argv` injects `[model_flag, model]` after the executable when both are set. `list_cli_models` runs `<cli> models` (or returns Claude's aliases) so the menu can show real available models.
- **Complexity-based model selection** (`resolve_call_model`, `models_by_tier`, `brain_next_action`'s `complexite` field) — per agent call, the brain also judges the sub-task as `simple` or `complexe`; `resolve_call_model(tool, complexity)` maps that to a model from the tool's `models_by_tier` (`{mini, strong}`), returning `(model, label)`. Precedence: a user-pinned model (`model_is_custom`) always wins (label `épinglé`); else `complexe`→`strong`, else `mini`; else the tool's own default. `ask_agent` applies the result to `tool['model']` before building/ displaying the command and shows the chosen tier + judged complexity in the step. Tools with `models_by_tier: None` (agy, vibe, mistral) get no auto-selection.
- **Local brain / Ollama** (`ensure_ollama`, `ollama_models`, `_http_get_json`, `_http_post_json`) — finds/auto-starts the local Ollama server (`http://127.0.0.1:11434`) and picks an installed model.
- **Orchestrator** (`brain_next_action`, `brain_synthesize`, `run_cli_headless`, `build_headless_argv`, `display_argv`, `ask_agent`) — the agentic loop. `brain_next_action` asks the LLM for the next step as JSON: either `{action:"call", cli, prompt}` or `{action:"final", message}` (tolerant parser recovers when the model returns a tool name / free text instead of the exact command). `build_headless_argv` renders a tool's `headless` + `auto_approve` (+ optional model) template into an argv; `run_cli_headless` executes it non-interactively (`.cmd`/`.bat` via a quoted shell string, else argv list) via `Popen`, reading stdout in a daemon reader thread + `queue.Queue` so the `timeout` fires even when the child emits nothing; with `stream=True` it prints each line live as it arrives while still returning the full captured output. `ask_agent` runs the confirm-each-call loop (capped by `AGENT_MAX_STEPS`), then `brain_synthesize` forces a final answer from the collected results.
- **Keyword fallback** (`route_with_keywords`, `route_query`, `KEYWORD_ROUTES`) — single-step routing used only when Ollama is unreachable; `route_query`/`route_with_ollama` remain for that offline path.
- **`EXTRA_PATHS`** — extra Windows directories (`%APPDATA%\npm`, `%USERPROFILE%\.local\bin`, `%LOCALAPPDATA%\agy\bin`) searched when a tool isn't found via `shutil.which` on `PATH`.
- **`find_tool_path` / `get_tool_version`** — detection: locate each tool's executable, then run it with `--version` (with special handling for `.ps1` via `powershell -File` and `.cmd`/`.bat` via `shell=True`) to capture its version string.
- **`create_desktop_shortcut` / `check_and_create_shortcut`** — builds a `.lnk` shortcut on the user's Desktop via a PowerShell `WScript.Shell` COM call, pointing at the current Python interpreter and this script's absolute path (with `icon.ico`, resolved relative to the script's own directory, not the CWD).
- **`scan_tools` / `print_dashboard`** — scan all `CLI_TOOLS` and render the ANSI-colored table (index, name, status, version, command).
- **`run_tool`** — launches the selected tool interactively as a subprocess (dispatching on `.cmd`/`.bat`/`.ps1`/plain exe), optionally passing the agent's request as a positional argument (`prompt`), then returns control to the dashboard loop.
- **Ephemeral VPS mode** (`VPS_CONFIG`, `build_vps_plan`, `_vps_context`, `print_vps_plan`, `run_vps_session`, `_vps_execute_live`, `_run`) — the `[V]` menu. Spins up a disposable GCP `e2-micro` VM, clones a repo, lets the agent work, then destroys the VM. **Dry-run by default**: `run_vps_session` prints the full command plan and creates nothing unless the user types `EXECUTER` and confirms (and `gcloud` is found). `_vps_execute_live` runs the real lifecycle (keygen → create → get IP → ssh clone → hand off → teardown) with the VM+disk deletion and local-key cleanup in a `finally` block so a VM is never leaked. The live path is gated and unverified against a real GCP project.
- **`main`** — the REPL loop: rescan, redraw, prompt for a menu choice (`N°` to launch a CLI interactively, `A` to ask the orchestrator agent, `M` to configure per-CLI models, `V` for an ephemeral cloud VPS session, `R` to refresh, `Q` to quit).

Windows-specific concerns handled explicitly at the top of the file: enabling ANSI escape codes via `kernel32.SetConsoleMode`, and reconfiguring stdout/stderr to UTF-8 for emoji rendering.

## Notes for changes

- Keep the script stdlib-only (no `pip install` dependency) unless there's a strong reason to add one — the whole point is a zero-setup double-click tool. The LLM router talks to Ollama over plain HTTP with `urllib` (stdlib); Ollama is an optional external program, not a Python dependency, and the agent degrades to keyword routing when it's absent.
- Icon path resolution (`icon.ico`) must stay relative to `os.path.dirname(os.path.abspath(__file__))`, not the working directory, since the desktop shortcut can launch the script from any CWD.
- README.md is in French; keep user-facing strings (prompts, dashboard labels) in French for consistency with the existing UI.
