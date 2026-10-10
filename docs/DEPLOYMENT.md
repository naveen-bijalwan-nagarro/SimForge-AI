# Single-host cloud deployment — no Docker

This deployment pattern works on a Linux VM with persistent storage. AWS EC2 or Lightsail are examples; it is not coupled to an AWS service. No cloud account, payment or resource has been provisioned by this repository.

## 1. Prepare the host

Scenario Lab uploads need no extra service: PDF/DOCX/text extraction uses the existing Python runtime and isolated 15-second subprocesses. Originals are not retained. Keep SQLite and backups private because extracted references and saved runs may contain business information. The supplied `deploy/Caddyfile` limits every request to 1 MB, so document uploads will be blocked until its proxy rule is adapted to permit up to 12 MB for `/api/scenario-documents` (base64 JSON overhead); application limits remain 2 MiB per file, 8 MiB per batch and 8 files. Keep the 1 MB limit for other write endpoints. Do not expose `data/` or backup paths as web assets. Browser voice dictation needs supported browser/microphone permissions and normally HTTPS; it may use the browser provider's network speech service. Typing works without it.

Use a supported Linux image with Python 3.12+, `venv`, Node.js 22+ and npm. Install a TLS proxy such as Caddy using its official installation instructions. Package names differ by Linux distribution.

Copy application source to `/opt/simforge/SimForge-AI`. Exclude `.venv`, `node_modules`, local `data`, `artifacts` and `.env` secrets. Keep `backend/builtin/training_catalog.yaml` and `backend/builtin/training_generator.py`: these contain the preserved training catalogue and generator. No `legacy/` directory is required. Keep the bundled scenario packs, `codex_sandbox/` templates, policies and synthetic sample reference packets as well.

```bash
cd /opt/simforge/SimForge-AI
bash scripts/setup.sh
```

The production bundle is `frontend/dist`. Node and npm are build-time requirements only once that directory exists. Run source installation before enabling the service, so the application discovers the built assets at startup.

## 2. Configure service identity and durable storage

Create an unprivileged `simforge` service user and a local persistent directory `/var/lib/simforge` owned by that user with mode `0700`. Allow the user to read the application code and virtual environment. Keep code read-only for the service account.

Create `/etc/simforge.env`, readable only by the service user/root, containing a unique initial administrator password of at least 14 characters:

```text
SIMFORGE_ADMIN_PASSWORD=replace-with-a-unique-long-secret
```

The example systemd unit sets `SIMFORGE_ENV=production` and `SIMFORGE_DATA_DIR=/var/lib/simforge`. Production cookies are HTTPS-only. **Do not reuse the development database**: the service deliberately rejects the demo-account marker.

Install `deploy/simforge.service` into `/etc/systemd/system/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now simforge
sudo systemctl status simforge
```

After the initial administrator has been created, the bootstrap password environment variable is not needed to restart the service. Changing it does not rotate an existing password. Account recovery currently requires an administrator-operated DB maintenance procedure; implement a password-reset workflow before broader rollout.

## 3. Add HTTPS

Set DNS for your chosen hostname to the VM. Adapt `deploy/Caddyfile`, validate it with Caddy, and reload the proxy. It forwards only to `127.0.0.1:8000`. Allow ports 80/443 through the host/cloud firewall; do not publicly expose port 8000. Caddy can obtain a certificate when DNS and ingress are correctly configured.

Sign in to `https://your-hostname` as `admin` with the bootstrap password. Do not send production passwords over a plain HTTP remote connection.

## 4. Add users

Admin-only `POST /api/users` accepts `username`, `name`, `password` (14+ characters), and role `learner` or `admin` (the combined Admin / Trainer). There are exactly two roles. Use a signed-in admin session and include `X-SimForge-Request: 1`. A UI account-management screen is not yet included. The browser's same-origin admin session can be used from an approved internal provisioning client. Do not put real passwords in shell history.

Administrators can inspect all runs and datasets in this single workspace; learners access their own. Administrators cannot advance, diagnose or make decisions in learner-owned runs. This is not a multitenant authorization model.

### Scenario authoring without a server-side Codex installation

Set `SIMFORGE_OPENAI_ENABLED=1` explicitly in production. Provision `OPENAI_API_KEY` using the service environment or a secret manager, and optionally `SIMFORGE_OPENAI_MODEL` (default `gpt-4.1-mini`). Keep secrets out of source control and browser-side variables.

Codex remains the default primary; no CLI failure automatically triggers an API request. Admin / Trainer explicitly chooses Use OpenAI API backup, then Generate draft with OpenAI API. This flow can also enter a masked key over HTTPS. UI keys are memory-only, not SQLite; they disappear on restart. Removing a transient key does not remove a file/environment-managed key. Generation may incur API charges and depends on model/project access; saving a key is not live connection validation.

For file-based persistence, provision `/var/lib/simforge/secrets/authoring.local.toml` from `config/authoring.example.toml`, with a fresh replacement key. Use a service-user-owned directory with mode 700 and file mode 600. Alternatively set `SIMFORGE_AUTHORING_CONFIG` to a private absolute path. Keep the file out of the copied code/bundle and unprotected backups. The API adapter reads it without putting its key in Codex child environments. Environment credentials override the file; a UI memory override overrides both. A plaintext file is not a secrets vault; prefer a managed secret for broader deployment.

### Upgrading from the three-role edition

Back up the existing database first. Startup changes legacy trainer-role accounts to learner, revokes their sessions and preserves IDs, resources and ownership. It does not automatically grant admin privileges. Use an existing administrator to provision a combined Admin / Trainer account if needed. Fresh databases seed only admin/learner development accounts; never use a demo-seeded database in production.

## 5. Back up and recover

Use SQLite's online backup API rather than copying only the main file while WAL is active:

```bash
SIMFORGE_DATA_DIR=/var/lib/simforge .venv/bin/python scripts/backup.py /secure-backups/simforge-2026-09-28.sqlite3
```

Backups include user password hashes, active session records and scenario data. Protect them as application data. Copy them to your chosen durable backup storage and test a restore into a separate data directory. Back up `data/exports` separately if those exported artifacts must be retained. Run backups under an identity with legitimate read access, and follow your retention requirements.

## Capacity and limits

- Start with one Uvicorn worker; this is a limited-pilot, single-host architecture.
- On startup, unfinished authoring, Codex-sandbox and SOP-factory jobs are marked failed with a restart explanation. Inputs and earlier progress remain available; no model calls are automatically retried. Completed drafts and learner simulation clocks are preserved. Do not run multiple workers against this single-worker job lifecycle.
- SQLite uses WAL with a 20-second busy timeout. DB writes are short; stale run versions return HTTP 409.
- Every world read/advance reconstructs a bounded run. The supplied benchmarks measure engine CPU time, not simultaneous browsers, file transfers or storage growth.
- Resource lists return the latest 200 items; audit returns 100. There is no pagination/retention management UI yet.
- Population is capped at 5,000 and horizon at 120. Large job queues may not drain inside that horizon.
- The API bounds structured payloads and has a request header/size guard. The example reverse proxy adds a 1 MB body limit. Set request/concurrency limits at the proxy for Internet exposure.
- Sign-in throttling is per observed client address. Review trusted proxy/address configuration before relying on it for larger deployments.
- SQLite resides on a **local persistent disk**, not NFS/EFS or ephemeral serverless storage. Multiple application replicas need a different DB/queue architecture.

## Scope of production readiness

The supplied configuration is a deployable foundation, not a claim of an audited production platform. Enterprise SSO, MFA, password rotation/recovery, central logging, immutable audit storage, tenancy, retention controls, load tests and domain validation remain rollout work. Choose these based on your actual pilot requirements. No external professional decision should rely on the illustrative simulation scores.

Reference: [FastAPI server deployment](https://fastapi.tiangolo.com/deployment/manually/).
