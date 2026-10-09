# Codex sandbox

A local workspace where the Codex CLI (signed in with your ChatGPT account) authors new SimForge
use cases through the `simforge` MCP server. Codex can only write inside this folder; it can
validate, test and **submit drafts for approval** but never publish.

## Start an interactive session

```powershell
.\scripts\codex-sandbox.ps1          # Windows
```
```bash
bash scripts/codex-sandbox.sh        # Linux / macOS
```

Then describe the world you want, for example:

> Create a Minecraft-style block world where a collapsed mine starves crafting and villagers need shelter.

Codex follows `AGENTS.md`: it asks a few questions, drafts `drafts/<key>.yaml`, runs the tests until
they pass and submits the draft. An administrator publishes it in **Scenario studio → Review and
publish**, and learners are notified.

## Without Codex

```powershell
.\.venv\Scripts\python.exe scripts\scenario_kit.py new my_world --title "My world"
.\.venv\Scripts\python.exe scripts\scenario_kit.py test codex_sandbox\drafts\my_world.yaml
.\.venv\Scripts\python.exe scripts\scenario_kit.py submit codex_sandbox\drafts\my_world.yaml
```

The web UI also has a guided builder (Admin → Codex sandbox) that works offline.
