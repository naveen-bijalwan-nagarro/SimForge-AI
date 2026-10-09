# Dependencies, attribution and data provenance

No paid software license, API subscription, GPU toolkit, external dataset or licensed enterprise database is required for the active runtime. Open-source dependencies still carry license obligations. This document is an inventory, not a new license grant over the project.

## Python runtime (pinned in `requirements-lock.txt`)

| Component | License | Purpose |
|---|---|---|
| FastAPI, Starlette, Pydantic | MIT | HTTP API and validation |
| Uvicorn | BSD-3-Clause | ASGI server |
| SimPy | MIT | Discrete-event clock and resource queues |
| NetworkX | BSD-3-Clause | Dependency, scenario and relationship graphs |
| Mesa | Apache-2.0 | Agent-based populations |
| NumPy, SciPy, scikit-learn | BSD-3-Clause | ML failure lab, metrics, image features |
| Pillow | MIT-CMU (HPND) | Procedural images and GIF clips |
| LangGraph, LangChain Core | MIT | SOP-factory state machine |
| MCP Python SDK | MIT | SimForge MCP tool server |
| Faker | MIT | Synthetic text fields and the original generator |
| PyYAML | MIT | Scenario packs and the original catalogue |
| pypdf | BSD-3-Clause | PDF SOP text extraction |
| SQLite | Public domain (Python wrapper under the PSF license) | Persistence |

## Browser (pinned in `frontend/package-lock.json`)

| Component | License | Purpose |
|---|---|---|
| React, React DOM | MIT | Interface |
| Three.js, @react-three/fiber, @react-three/drei | MIT | Live WebGL 3D world |
| deck.gl (@deck.gl/react, core, layers) | MIT | Agent population layers |
| Apache ECharts | Apache-2.0 | Charts |
| Cytoscape.js, cytoscape-dagre | MIT | Graphs |
| Lucide React | ISC | Icons |

Vite, the React plugin, Prettier, Playwright, pytest, httpx and Ruff are development/build/test tools.

## Optional tools (not installed by default)

| Tool | License | Use |
|---|---|---|
| Codex CLI | See OpenAI terms | Scenario engineer, repairs, sandbox authoring (your ChatGPT plan limits apply) |
| Microsoft Presidio | MIT | Additional PII recognizers (with a spaCy model) |
| PostgreSQL + pgvector, psycopg | PostgreSQL License; LGPL-3.0 (psycopg) | Alternative knowledge-base store |
| Open Policy Agent | Apache-2.0 | Evaluates `policies/publish.rego` |
| Promptfoo | MIT | Runs the exported red-team suite |
| pyarrow | Apache-2.0 | Parquet export for pandas users |

Tools named as scenario *building blocks* (CALDERA, CloudGoat, Chaos Mesh, LocalStack, OpenFAST, Grid2Op, PyPSA, PX4, ROS 2, SUMO, CARLA, Covasim, Synthea, Nextflow, DeepVariant, msprime, RDKit, DeepChem, PK-Sim, EPANET, ns-3, ABIDES, OpenTTD, MVTec AD, …) are **not** installed, downloaded or executed. Check each one's license before integrating it; MVTec AD, for example, is non-commercial.

## Application source

The original SafeSim catalogue and generator were copied into `backend/builtin/` (the archival `legacy/` folder has since been removed from this repository). No new blanket license was applied to the user's pre-existing work.

## Data

- All world populations, evidence, images, datasets, ML-lab data and SOP examples are generated locally and synthetic.
- No UCI, NASA, healthcare, banking, game-player, genomic, clinical or security dataset was downloaded.
- The demo SOP contains fictitious personal data solely to demonstrate sanitization.
- Bootstrap/independent CSV synthesis in the Generator lab can retain source values; it is not certified anonymization. Use synthetic or approved non-sensitive source rows.
