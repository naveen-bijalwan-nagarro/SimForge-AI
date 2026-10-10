# SimForge AI — Scenario Lab

A CPU-first mock-data training environment: **Admin / Trainer creates and publishes; Learner investigates, acts and reviews objective learning evidence.**

Exactly two application roles. One authoring page. FastAPI + React/npm + SQLite. No Docker, GPU or external database is needed for the core simulation. Optional browser WebGL views are separate from the CPU simulator.

## The simple flow

1. **Admin / Trainer → Scenario Lab:** choose Codex CLI, OpenAI API or manual JSON. Describe the learning mission, systems and hidden incident; create the draft.
2. **Check and publish, on the same page:** inspect source, author, version, mission, workflow and validation results. Failed checks block publication. Publish to notify learners.
3. **Learner:** open the notification, understand the mission, generate linked datasets and enter the simulation.
4. Investigate observed records and evidence, diagnose the fault, choose a response and observe its cost, delay and consequences.
5. Complete the run to compare with the **same workload without intervention**, reveal the hidden cause and export the debrief.
6. **Admin / Trainer → Assignments & results:** assign guidance and observe the learner's run without changing their decisions or clock.

There are **no separate SOP factory, From an SOP, Advanced builder or Codex sandbox pages** in this edition. Their older backend engines remain compatibility/internal components, not extra demo steps. ML exercises appear within Scenario library and retain their distinct investigation/scoring engine.

Use [the four-minute presentation script](docs/HACKATHON_DEMO.md). Scenario Lab starts with a blank brief and a domain-neutral editable workflow. Generated definitions automatically replace the editor contents.

### Hackathon demo packets

For the short round-trip demo, paste the [CloudRescue admin prompt](samples/sample2/admin_prompt.txt) into **Scenario Lab** and upload its single [synthetic incident brief](samples/sample2/CloudRescue_Incident_Brief.docx). The brief contains a fictional contact, reserved-domain email and test-network address for the local text-screening preview and type/count security receipt. Follow the [sample2 learner route](docs/SAMPLE2_LEARNER_ROUTE.md) to commit Inspect, diagnosis and Repair before completing the run. The smaller packet reduces reference text but does not guarantee Codex generation speed.

For a richer manufacturing example, paste the [FactoryPulse admin prompt](samples/sample1/admin_prompt.txt) and upload the [operations brief](samples/sample1/FactoryPulse_Operations_Brief.docx) and [sensor charts](samples/sample1/FactoryPulse_Sensor_Charts.pdf). The [synthetic privacy examples](samples/sample1/FactoryPulse_Privacy_Examples.docx) are optional for demonstrating screening. Both packets are Admin / Trainer upload inputs, not built-in publications. Generation, review and publication remain explicit actions. Follow the [four-minute recording plan](docs/HACKATHON_DEMO.md).

**Learning journey:** mission and success criteria → three-question starting check → evidence, diagnosis and response → outcome and three-question post-check. Four score cards stay above the simulator: starting knowledge, post-check knowledge, objective learning score and knowledge change. No free-text answer or manual grading is required; Admin / Trainer assigns and observes rather than scoring answers.

The **100-point practice score** for this live simulation is calculated on the server: post-check **50**, correct incident diagnosis before debrief **25**, logged investigation after incident onset and before response **15**, targeted repair with time to take effect **10**. The learner report shows the actual score and each measured contribution as a bar with earned and available points. Trade-off reasoning and knowledge transfer are shown as unscored follow-up areas; the report does not invent percentages or trainer-review status. Knowledge change is the actual before/after percentage-point difference, not this composite score. Missing baseline is unavailable, not zero; zero and negative change remain visible. Answer keys are only returned after the post-check is submitted. New questions use the frozen scenario title, role, work-item type and workflow handoffs without quoting the hidden incident or cause. This is a short operational-reasoning practice check, not a validated domain exam or certification; measure transfer and retention later on an unseen exercise.

### Knowledge checks across Scenario Library

Every Scenario Library format offers a three-question starting check before practice evidence and a three-question post-check after the main task. The questions use the exercise context and a hypothetical follow-up variation; they do not turn a practice result into a certification. Starting knowledge and post-check knowledge are percentages. **Knowledge change** is their difference in percentage points when both checks were recorded; a missing starting check stays unavailable. The learner report keeps that comparison separate from the exercise's own 100-point practice score. Answer keys appear after the post-check.

| Library path | Post-check opens after | Existing practice score |
|---|---|---|
| Live simulation, including a historical case opened in live mode | The simulation reaches its horizon | Post-check 50 · timely correct diagnosis 25 · investigation before response 15 · targeted repair 10 |
| Historical data investigation | The first case assessment is submitted | Root-cause finding 55 · evidence 25 · recommendation 20. Later case attempts remain in history but do not rewrite the first-attempt learner report. |
| ML investigation | The learner submits a failure diagnosis and fixes | Failure diagnosis 45 · recovery 35 · fix precision 10 · investigation efficiency 10 |

For a new historical case or ML lab, complete the starting check before opening evidence, or explicitly continue without it. Older case files and labs retain their existing scores and can take the post-check, but cannot retroactively gain a starting check, so knowledge change is unavailable. Scores and synthetic outcomes are illustrative practice evidence; an unseen later exercise and retention check are still needed to establish learning transfer.

The learner's primary tabs are **Operations**, **Evidence**, **Diagnose & act**, and **Learning review**. Live operations opens the mock application for ordinary workflows, with an **Application / System map** switch for the diagram; block-style worlds open the map first. The switch changes presentation only and also works for previously saved runs. Additional data, 3D, timeline and council views are grouped under **Data & visual tools**. The dedicated agent-population screen/API and Mesa/deck.gl dependencies are removed from the active experience; a legacy population module remains in source but is not used by the current learner API. Synthetic work-item volume remains part of dataset generation.

Learner notifications, the library, assignments and run views refresh in place while visible. **Refresh notifications**, **Refresh library**, **Refresh progress**, **Refresh runs** and **Refresh view** provide an immediate fetch without advancing the simulation clock. Loading states wait for the current published scenario, evidence and debrief before showing their content; the live work queue opens after playback begins. **Complete run** warns if a diagnosis, incident-time Inspect action or targeted Repair is still missing, so the learner can cancel and record those actions before the hidden cause is revealed.

If the UI reports that the running backend is out of date, stop this project's server and restart with `start.cmd` or `scripts/start.ps1`, then refresh the browser. Rebuilding React alone does not reload Python routes. `/api/health` reports `api_contract: scenario-lab-objective-v3` for this authoring version. Use `scripts/start.ps1 -Dev` or `-Reload` during local iteration.

The same versioned [system prompt](config/scenario_authoring_system.txt) guides both providers to create a compact 5–7-node definition. Python generates linked data and consequences; learner runs require no model or API key. Smaller models still need a supported structured-output interface, account access and human review; generation speed/quality are not guaranteed. Use **Edit and revalidate** to repair a checked draft while preserving provenance. Re-entering the learner library refreshes publications, and notifications fetch the current scenario when opened.

## Quick start — Windows

Requirements: Python 3.12+ and Node.js 22+ with npm for setup/build. A Codex installation is optional.

~~~powershell
./setup.cmd
./start.cmd
~~~

Open the address printed by start. Start serves the built React UI and API from one Python process; it rebuilds changed frontend sources. The API docs are at /docs.

Development accounts only:

| Role | Username / password | Purpose |
|---|---|---|
| Admin / Trainer | admin / admin123 | Create, validate, publish, assign and observe |
| Learner | learner / learner123 | Generate data, run published scenarios and make decisions |

Use separate browser profiles or a private window for simultaneous roles. Tabs in one profile share their sign-in cookie. Header and sidebar **Log out** end the SimForge session; Codex sign-out is a separate, explicitly confirmed action.

For source development, run the backend and Vite separately:

~~~powershell
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
~~~

In another terminal:

~~~powershell
cd frontend
npm install
npm run dev
~~~

Vite proxies /api to the backend. For a single-server build use npm run build, then launch Python after frontend/dist exists. Node is build-time only once the bundle is created.

If a memory-constrained Windows machine cannot finish Vite's minified build, run `$env:NODE_OPTIONS='--max-old-space-size=1536'; npm.cmd run build -- --minify false` from `frontend`. This still creates a production bundle, with larger asset files.

## One Scenario Lab, three authoring engines

| Engine | Needs | What it does |
|---|---|---|
| Codex CLI | Installed, signed-in CLI; enabled authoring; available plan quota/network | Produces a constrained JSON scenario definition in read-only mode |
| OpenAI API | An API key and accessible structured-output model; network | Calls the Responses API from Python; no CLI installation required |
| Manual scenario | Nothing external after dependency installation | Saves a manually editable, deterministic template as a checked draft |

**Codex is always the primary/default on opening Scenario Lab.** If unavailable or a draft fails, the admin can choose **Use OpenAI API backup**. Switching providers alone sends no prompt; an explicit **Generate draft with OpenAI API** action is required. There is no automatic failover, silent API retry or hidden API charge. **Return to primary Codex** switches back.

All three converge on the same validation/publication queue. Sources are recorded as **codex**, **openai_api** or **manual**. API requests are not represented as Codex CLI activity. Generated Python, JavaScript or shell commands are **not executed** by the Scenario Lab. A definition still needs human subject-matter review.

**Codex connection:** select Codex CLI in Authoring engine. Enable authoring, sign in using the official browser/device-code flow, refresh status and choose a model exposed by the installed CLI. Production CLI authoring requires SIMFORGE_CODEX_ENABLED=1. No global Codex model configuration is overwritten.

**API connection:** select OpenAI API. Enter the key in the masked admin-only input, choose a model and Save API connection. The input clears after submission. Saving does not make a generation request or prove model access; Generate draft with OpenAI API verifies access and may incur API charges. The default model ID is gpt-4.1-mini; availability is subject to your API project.

### Multiple scenario documents and voice dictation

In **Scenario Lab → Upload scenario documents**, select multiple PDF, DOCX, TXT, Markdown, CSV, JSON, PNG, JPEG or WebP files in the same picker. Limits: 8 files per batch/selected draft, 2 MiB per file and 8 MiB per batch. PDFs must have selectable text (up to 80 pages); scanned PDFs need OCR outside the app. Images need an administrator-reviewed description of at least 30 characters and at most 8 million pixels. Only that screened description reaches the model; image pixels and metadata are discarded after local validation. No automatic OCR, visual interpretation or visual PII detection is claimed. Encrypted, malformed and macro/legacy DOC files are rejected. DOCX extraction reads text without executing macros or following links.

Extraction runs locally in time-limited Python subprocesses. Preview each document, inspect warnings and deselect references you do not want included. Common PII patterns are redacted before storage, but detection is incomplete: upload only authorized, non-sensitive/synthetic material. Only bounded extracted text, a file hash and metadata are stored in SQLite; original files/audio are not retained. Uploaded text is untrusted reference data, not instructions or executable code. It does not become a general-purpose knowledge base or train a model.

The authoring form lists only files uploaded in the current session. Earlier extracted uploads remain in the local store for provenance but are not shown or selected automatically. Upload the desired files again for a new draft; only checked references are sent to preview or generation.

**System prompt and safety rules** shows the shared, versioned server prompt used by both authoring engines. Learners run CPU simulations without inference. The **Security review** log shows local brief/reference scans before provider access, output screening, instruction-override checks and explicit administrator publication approval. Scan receipts display status, detector, recognized entity types and counts, timestamp and selected reference name where available; matched values are never logged. Uploaded reference cards show their own text-screening receipts. Revisions retain the input screening provenance. Publication repeats privacy/governance checks before committing the scenario and notifying learners.

**Preview privacy checks** screens the typed brief locally before generation. Generation automatically runs the visible preflight, and the provider endpoint independently screens its input again. The sanitized preview does not overwrite the admin's typed brief. Built-in recognizers cover titled person names, email, phone, labelled account and birth-date fields, Indian PAN, Aadhaar-shaped identifiers, Luhn-valid payment-card numbers, IBAN, US SSN, IP addresses and common secret/token forms. Optional Presidio detection is reported only when installed. Findings contain counts and types, never original matches. Zero matches does not establish that text is PII-free; image pixels and scanned PDF pages are not screened. Generated scenario content is checked for known instruction overrides before publication. These controls complement admin review; they do not establish complete anonymization or prompt-injection immunity.

An explicit Codex/API **Generate draft** sends only the selected text excerpts with your learning-goal description. The 24,000-character reference budget is shared fairly between selected documents; extraction itself keeps up to 24,000 characters per file. The draft/publication records source names, hashes and excerpt status; this provenance accompanies the published scenario. Full documents are not guaranteed to fit; review the generated workflow against your sources. Manual JSON does not interpret uploaded references. Extracted source content is private to the uploading administrator; published provenance is visible with the exercise.

**Write with your voice** dictates into the editable Admin prompt. Choose English (India/US) or Hindi, acknowledge browser speech processing, Start voice dictation, then Stop and review/edit before generating. Voice never publishes scenarios or invokes model calls automatically. Browser support varies and microphone access normally requires HTTPS or localhost. The browser may use a remote speech service; this is **not guaranteed offline** and language support depends on the browser. SimForge has no paid transcription dependency and stores no audio. Typing remains available if unsupported/permission denied. See [browser SpeechRecognition limitations](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).

### Fresh publication queue — recoverable archive

The upload boundary follows [OpenAI's guidance on untrusted input, structured outputs and human review](https://developers.openai.com/api/docs/guides/agent-builder-safety); these controls reduce risk but do not guarantee prompt-injection immunity.

Open **Fresh demo: archive previous custom scenarios** in Scenario Lab. Inspect the exact preview and type **ARCHIVE** to archive custom publications, drafts and completed/failed authoring history. Generation still running blocks cleanup; a changed queue requires a new preview. The active publication queue and custom library are cleared, and old related notifications/assignments are hidden. Built-in exercises, uploaded references, learner runs and datasets are not removed. Learners can reopen frozen prepared environments and existing runs even after archival. **Restore archive** recovers the queue/publications; this is not permanent deletion or a factory reset. Retention of sources/history means archival is not a privacy erasure request.

Before production maintenance, use the SQLite backup script and protect backups as carefully as the database. See [deployment](docs/DEPLOYMENT.md). The current demo cleanup is recorded in [verification](docs/VALIDATION.md).

### API credential safety

- The browser submits credentials to **your backend**, not directly to OpenAI. The application does not put keys in browser storage or return them in settings responses.
- UI-entered keys live in backend memory until cleared/restarted; **they are not saved in SQLite or audit records**.
- For durable production configuration, prefer OPENAI_API_KEY from a server environment/secret manager. The private backup file below is also supported. Never put a key in source code, public frontend variables, prompts or version control.
- Remove memory-only key clears only the UI-supplied key. A private-file or environment key is managed by the server and can remain configured.
- Production must explicitly set SIMFORGE_OPENAI_ENABLED=1 and use HTTPS. SIMFORGE_OPENAI_ENABLED=0 disables this provider.
- Outbound requests use the fixed official API origin with TLS verification, no redirects, bounded responses, a timeout, a token cap and **no automatic retries**. Provider errors/refusals/incomplete outputs fail closed and are redacted.
- API authoring has separate API usage/billing. The simulation itself runs locally without provider calls.

Implementation follows [OpenAI structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs), [server-side key guidance](https://developers.openai.com/api/reference/overview) and the [model's documented capabilities](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

### Persistent API backup configuration

Default private file: **data/secrets/authoring.local.toml**, relative to SIMFORGE_DATA_DIR. A blank local file is prepared in this checkout; other installations can copy [the non-secret example](config/authoring.example.toml) there. Put a **fresh replacement key** in its api_key field locally—do not paste keys into chat. Revoke any key already shared in chat before use.

~~~toml
[openai_backup]
api_key = ""
model = "gpt-4.1-mini"
~~~

The backend reads this file directly without exporting its credential into environment variables or Codex child processes. The file is Git-ignored, outside the served React assets, and is never returned by the settings API. Settings show only source/configured status/model, not the credential. Read/parse failures are redacted and block that file's backup.

Credential priority is **UI memory override → OPENAI_API_KEY environment → private file**. UI model overrides and SIMFORGE_OPENAI_MODEL take precedence over the file model. Clearing a UI key reveals the underlying server configuration; it does not erase the file. File configuration survives backend restarts, but cannot change the primary provider or enable automatic failover.

For a custom private location, set **SIMFORGE_AUTHORING_CONFIG** to its full path (for example /etc/simforge/authoring.local.toml). On Linux, use a service-user-owned secrets directory with mode 700 and file mode 600; a non-empty key in a group/world-accessible file is refused. On Windows, restrict its directory/file ACL to the service account and SYSTEM; the prepared local file is restricted to the current Windows user and SYSTEM. The file is plaintext, not a vault: include it only in protected backups and prefer a secret manager for production. Production still requires SIMFORGE_OPENAI_ENABLED=1 and HTTPS.

## Are the datasets already generated?

**Scenario definitions are preloaded; each learner's records are generated on demand.** New admin-published scenarios use the same pipeline—there is no requirement to ship a prebuilt CSV for every new exercise.

1. Open a published scenario and choose a seed, workload size and simulation horizon.
2. Generate scenario datasets creates linked synthetic people, teams, assets, systems, work items, workflow steps, dependencies and response options; relevant domain tables are added where supported.
3. Inspect the manifest, relationship checks and records before entering the simulation.
4. The simulator consumes that **exact saved workload**, not a second random generation. Live telemetry, transitions and source events appear as time advances.
5. The prepared environment is persisted in SQLite. **Training datasets → Scenario-generated datasets** lets you reopen it, inspect records and start another run. Same seed/specification preserves reproducibility. Administrators may inspect learner-owned environments but must generate their own workload for a preview run.
6. Historical data investigations are another exercise type: case files with no simulation clock, scored for root cause, evidence and recommendations.

Training datasets shows both saved scenario environments and historical case files. New custom scenarios support live linked-data simulations; they do not automatically gain a bespoke historical assessment rubric.

Lists, preparations and audit records have separate caches, loading/error states and retry actions. Stale responses cannot replace another list; logout invalidates pending list requests. Dataset detail state is keyed by its ID.

## Roles and permissions

Only **admin** and **learner** are accepted for new users.

| Capability | Learner | Admin / Trainer |
|---|:-:|:-:|
| View published exercises and generate their own training data | ✓ | ✓ |
| Make decisions and control an owned simulation | ✓ | ✓ |
| Create, validate and publish scenarios; configure AI connections | | ✓ |
| Assign exercises and view learner results | | ✓ |
| Modify a learner-owned run while observing | | |
| Manage accounts, integrations and audit | | ✓ |

Permissions are enforced by the API, not just navigation. Administrator-owned preview runs remain editable. The workspace is single-tenant; administrators can inspect learner resources.

**Existing installations:** startup migrates legacy trainer-role accounts to **learner**, revokes their sessions and preserves IDs, records and resource ownership. It does not silently grant administrator privileges. A current administrator can provision a combined Admin / Trainer account when needed. Back up the DB before upgrading; see [deployment](docs/DEPLOYMENT.md). Fresh development databases contain just the two demo accounts.

Legacy factory/sandbox/designer subpage bookmarks resolve to the single Scenario Lab. A learner cannot use those URLs to author scenarios.

## Learner experience and impact

Main views are Operations/mock application, Evidence, Diagnose & act and Learning review. Optional datasets, 3D, timeline, agent council, charts and graph tools remain available. Agents recommend; humans commit. The learner's simulation clock is server-anchored and survives closing the browser.

The baseline comparison, synthetic costs and scoring are **illustrative training outcomes**, not proven customer savings or a certified digital twin. Validate with a pilot: diagnosis time, assessment improvement, trainer preparation minutes and user feedback. Do not claim pilot evidence before collecting it.

The library currently has 55 live worlds, 20 historical cases and 59 ML investigations. Dataset Studio, Scenario graph, generator/integration/audit tools remain under Advanced tools; they are not required for the four-minute demo.

## Configuration and deployment

| Setting | Purpose |
|---|---|
| SIMFORGE_DATA_DIR | Local persistent directory for SQLite and generated artifacts |
| SIMFORGE_ENV=production | Production credentials/cookies; refuses demo-seeded databases |
| SIMFORGE_ADMIN_PASSWORD | Initial production administrator password, 14+ characters |
| SIMFORGE_CODEX_ENABLED=1 | Opt into CLI authoring on the server |
| SIMFORGE_CODEX_EXECUTABLE | Optional absolute path to the CLI binary |
| SIMFORGE_OPENAI_ENABLED=1 | Required production API-authoring opt-in |
| OPENAI_API_KEY | Server-side persistent API credential |
| SIMFORGE_OPENAI_MODEL | API model default; gpt-4.1-mini if unset |
| SIMFORGE_AUTHORING_CONFIG | Optional full path to the private API-backup TOML file |

Use [single-host cloud deployment](docs/DEPLOYMENT.md) for a Linux VM such as EC2/Lightsail, HTTPS, durable disk, backups and systemd—**no Docker**. Setup downloads dependencies; core simulation runs offline afterward. Cloud infrastructure and API inference are not claimed to be free.

This is a **production-minded pilot**, not an audited enterprise platform. SSO/MFA, password recovery, multitenancy, retention management, centralized/immutable audit, monitoring, concurrency/load validation and domain validation remain rollout decisions. Use one worker; in-process authoring jobs require the documented restart recovery. SQLite must be on local persistent storage, not NFS or ephemeral serverless disk.

## Verification

~~~powershell
.venv/Scripts/python.exe -m ruff check backend scripts tests
.venv/Scripts/python.exe -m pytest -q
cd frontend
npm run build
npm run test:e2e
~~~

Browser tests require an installed Playwright browser, or SIMFORGE_BROWSER pointing to a browser executable and SIMFORGE_TEST_URL pointing to an isolated test server. Use a dedicated SIMFORGE_DATA_DIR. Space large batches to respect the unchanged 10-login-attempts/minute throttle.

Tests cover two-role publication/notifications/observation, on-demand linked data, durable navigation, historical assessments, ML/visual engines, Codex UI controls and the API adapter. API tests use a mocked transport; live Codex generation is opt-in via SIMFORGE_LIVE_CODEX=1. Passing mocked tests is not a claim that a real API key has been validated.

## Code and supporting references

- [Repository agent instructions](AGENTS.md) describe the working agreements and scenario-prompt checklist. Keep your own scenario material in numbered subfolders under `samples/`; use [adding use cases](docs/ADDING_USE_CASES.md) for version-controlled YAML packs.
- backend/main.py, studio.py, drafts.py: permissions, data preparation, runs, publication, notifications and provenance.
- backend/authoring.py, openai_authoring.py: CLI and Responses API adapters sharing a checked draft/job pipeline.
- frontend/src/Hackathon.jsx, Experience.jsx, OpenAIConnection.jsx: the single Scenario Lab, role guidance, data inspection and provider setup.
- [Validation history](docs/VALIDATION.md), [deployment](docs/DEPLOYMENT.md), [adding use cases](docs/ADDING_USE_CASES.md), [third-party libraries](docs/THIRD_PARTY.md) and [migration notes](docs/MIGRATION.md).
