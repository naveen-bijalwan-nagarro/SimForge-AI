# Source preservation and migration

## Two-role Scenario Lab upgrade — 9 October 2026

The active branch `hackathon/simforge-scenario-lab` accepts only `admin` and `learner` accounts. Admin is presented as **Admin / Trainer** and combines authoring, publication, assignments and observation. Startup converts old `trainer` accounts to **learner**, revokes their sessions and preserves their IDs and owned records. It never silently grants administrator access; provision an administrator account explicitly if needed. Back up the data directory before upgrading.

The separate Scenario studio/SOP factory/Advanced builder/Codex sandbox UI has been replaced with one **Scenario Lab**. Legacy authoring bookmarks normalize to that page, while old backend engines remain internal compatibility components. Existing scenario definitions, runs and datasets are preserved. API credentials supplied through the new UI are memory-only; persistence requires a server environment/secret manager, not database migration.

The sections below describe the original SafeSim migration history, not the current scenario count or role design.

The user authorized a copy of `D:\mywork\myideas\SafeSim_Studio_Proposal_Ready\safesim_studio` to the new `SimForge-AI` project. The original was not edited. The initial copy contained 73 files excluding the virtual environment, caches, Git metadata and real `.env` credentials.

## Active runtime

- FastAPI replaces Flask routes for the new interface.
- React replaces server-rendered templates in the new interface.
- Built-in `sqlite3` stores new resources; the copied Flask/SQLAlchemy database is not migrated automatically.
- The original `scenarios.yaml` and `generator.py` are loaded directly without importing Flask. Their source and behavior are preserved.
- Existing exact-answer training rubric is reproduced with disclosed limitations.
- New worlds are stored as structured JSON with immutable run snapshots.
- Original file/SQLite export use cases have new controlled implementations.
- The new synthesis lab implements bootstrap and independent sampling in the Python standard library.

## Archived, not silently claimed as migrated

The original Flask interface and user records remain in `legacy/safesim_studio`. Its advanced synthesis (including Gaussian copula and optional SynthCity), document-forgery utilities, external database/REST/S3 connectors, templates and proposal documents are preserved. They require their original dependencies and have not been validated in the new runtime. The new runtime provides no credential forwarding or outbound connector execution.

This preserves the complete source for later feature migration while keeping the requested active stack small. The new service never mounts the archive as static web content.

## New behavior

- 15 bounded dynamic worlds; five have specialized consequence rules and ten share a workflow template.
- NetworkX dependencies + SimPy finite processing capacity.
- Human-committed interventions, deterministic role agents, replay, forks and no-action comparison.
- Persistent session authentication, ownership, optimistic updates and audit history.

Changing simulation equations may change historical replay outcomes. The payload includes `engine_version=1`; freeze code with production backups or implement versioned dispatch before introducing incompatible model changes.
