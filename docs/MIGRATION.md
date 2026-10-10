# Source preservation and migration

## Two-role Scenario Lab upgrade — 9 October 2026

The current `main` branch accepts only `admin` and `learner` accounts. Admin is presented as **Admin / Trainer** and combines authoring, publication, assignments and observation. Startup converts old `trainer` accounts to **learner**, revokes their sessions and preserves their IDs and owned records. It never silently grants administrator access; provision an administrator account explicitly if needed. Back up the data directory before upgrading.

The separate Scenario studio/SOP factory/Advanced builder/Codex sandbox UI has been replaced with one **Scenario Lab**. Legacy authoring bookmarks normalize to that page, while old backend engines remain internal compatibility components. Existing scenario definitions, runs and datasets are preserved. API credentials supplied through the new UI are memory-only; persistence requires a server environment/secret manager, not database migration.

The sections below describe the original SafeSim migration history, not the current scenario count or role design.

The user authorized a copy of `D:\mywork\myideas\SafeSim_Studio_Proposal_Ready\safesim_studio` to the new `SimForge-AI` project. The original was not edited. The initial copy contained 73 files excluding the virtual environment, caches, Git metadata and real `.env` credentials.

## Active runtime

- FastAPI replaces Flask routes for the new interface.
- React replaces server-rendered templates in the new interface.
- Built-in `sqlite3` stores new resources; the copied Flask/SQLAlchemy database is not migrated automatically.
- The retained training catalogue and generator are loaded from `backend/builtin/training_catalog.yaml` and `backend/builtin/training_generator.py` by `backend/catalog.py`, without importing Flask.
- Existing exact-answer training rubric is reproduced with disclosed limitations.
- New worlds are stored as structured JSON with immutable run snapshots.
- Original file/SQLite export use cases have new controlled implementations.
- The new synthesis lab implements bootstrap and independent sampling in the Python standard library.

## Original application boundaries

The original Flask application and its user database are not included in the current checkout; the earlier `legacy/` folder was removed. The built-in training catalogue and generator remain in `backend/builtin/`. Advanced synthesis and external database/REST/S3 connectors from the original application are not active SimForge features. The current runtime does not migrate the old Flask user records or forward its credentials.

## New behavior

- At the initial migration, 15 bounded dynamic worlds were added; the current Scenario Library has expanded since then.
- NetworkX dependencies + SimPy finite processing capacity.
- Human-committed interventions, deterministic role agents, replay, forks and no-action comparison.
- Persistent session authentication, ownership, optimistic updates and audit history.

Changing simulation equations may change historical replay outcomes. New live preparations currently use `engine_version=2`; keep code and database backups together and add versioned dispatch before introducing incompatible model changes.
