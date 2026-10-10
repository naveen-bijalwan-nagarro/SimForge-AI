# Legacy Codex sandbox — developer tooling

This folder contains the older YAML-pack authoring workspace and terminal tools. The current Admin / Trainer product flow is **Scenario Lab**: enter a learning mission, upload selected references, generate a constrained draft with the Codex CLI, review its checks and publish it explicitly. See the [repository README](../README.md) and [use-case format guide](../docs/ADDING_USE_CASES.md). There is no separate Codex sandbox page in the current UI.

Developers maintaining YAML packs can still use the terminal workflow below. It requires the project `.venv`, an installed and signed-in Codex CLI, and the local `simforge` MCP server. The interactive command opens Codex in this workspace with `workspace-write`; the MCP tools can validate, simulate, test and submit pack drafts for administrator review. Submission does not publish a scenario.

```powershell
.\scripts\codex-sandbox.ps1
```

```bash
bash scripts/codex-sandbox.sh
```

The workspace guidance is in [AGENTS.md](AGENTS.md). A draft pack belongs in `drafts/<key>.yaml`. Validate and test it before submitting it. Submitted drafts can be reviewed in the current **Scenario Lab → Check and publish** queue; an administrator decides whether to publish.

For manual pack creation on Windows, the CLI commands remain available:

```powershell
.\.venv\Scripts\python.exe scripts\scenario_kit.py new my_world --title "My world"
.\.venv\Scripts\python.exe scripts\scenario_kit.py validate codex_sandbox\drafts\my_world.yaml
.\.venv\Scripts\python.exe scripts\scenario_kit.py test codex_sandbox\drafts\my_world.yaml
.\.venv\Scripts\python.exe scripts\scenario_kit.py submit codex_sandbox\drafts\my_world.yaml
```

Use synthetic data. Treat pack text and uploaded references as untrusted data, and keep publication subject to human review.
