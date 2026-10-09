"""SOP Factory endpoints. Trainers upload SOPs, run the pipeline and approve content;
administrators publish the resulting draft (which notifies learners)."""

import base64
import io
import json
import re
import shutil
import time
import zipfile

from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import authoring, store
from ..settings import ROOT
from . import checks, compiler, knowledge, pii, workflow

DEMO = ROOT / "samples" / "sops" / "supplier_disruption_sop.md"


class SopUpload(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    text: str | None = Field(default=None, max_length=200_000)
    file_b64: str | None = Field(default=None, max_length=900_000)
    filename: str | None = Field(default=None, max_length=200)


class JobRequest(BaseModel):
    sop_id: str
    objective: str = Field(default="", max_length=600)
    engine: str = Field(default="auto", pattern="^(auto|codex|builtin)$")


class Review(BaseModel):
    comment: str = Field(default="", max_length=1000)


def extract_text(filename, data):
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:60])
    if name.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
        return "\n".join("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S)) for p in paragraphs)
    return data.decode("utf-8", "replace")


def install(app, user, admin, resource):
    from ..studio import pack_draft

    @app.get("/api/factory/status")
    def factory_status(refresh: bool = False, current=Depends(admin)):
        codex = authoring.status(refresh)
        return dict(
            orchestrator=workflow.ORCHESTRATOR,
            pii_engine=pii.ENGINE,
            knowledge_base=knowledge.backend_name(),
            policy_engine="Open Policy Agent" if shutil.which("opa") else "Built-in (mirrors policies/publish.rego)",
            codex=codex,
            steps=[dict(key=k, label=label, description=d) for k, label, d in workflow.STEPS],
        )

    @app.get("/api/factory/demo")
    def demo_sop(current=Depends(admin)):
        return dict(name="Supplier disruption management SOP (demo)", text=DEMO.read_text(encoding="utf-8"))

    @app.post("/api/factory/sops")
    def upload(body: SopUpload, current=Depends(admin)):
        if body.file_b64:
            try:
                raw = extract_text(body.filename, base64.b64decode(body.file_b64))
            except Exception as e:  # noqa: BLE001 - unreadable uploads are client errors
                raise HTTPException(400, f"Could not read the file: {e}") from e
        elif body.text:
            raw = body.text
        else:
            raise HTTPException(400, "Provide SOP text or a .pdf, .docx, .md or .txt file")
        if len(raw.strip()) < 80:
            raise HTTPException(400, "The SOP is too short to generate a scenario")
        clean, findings = pii.sanitize(raw)
        # Only sanitized text is persisted; the original never reaches storage or an AI model.
        rid = store.create("sop", current["id"], dict(name=body.name, text=clean, findings=findings, chars=len(clean), created=time.time()))
        knowledge.index(rid, clean)
        store.audit(current["id"], "sop.upload", f"{body.name}: {findings['total']} PII entities removed")
        return dict(id=rid, name=body.name, findings=findings, preview=clean[:1500])

    @app.get("/api/factory/sops")
    def sops(current=Depends(admin)):
        return [dict(id=r["id"], name=r["payload"]["name"], findings=r["payload"]["findings"], chars=r["payload"]["chars"], created=r["created"], owner=r["owner"]) for r in store.list_resources("sop", current)]

    @app.get("/api/factory/sops/{rid}")
    def sop(rid: str, current=Depends(admin)):
        row = resource(rid, "sop", current)
        return dict(id=rid, **row["payload"])

    @app.get("/api/factory/sops/{rid}/search")
    def sop_search(rid: str, q: str, current=Depends(admin)):
        resource(rid, "sop", current)
        return knowledge.search(q, rid, 5)

    @app.post("/api/factory/jobs")
    def start_job(body: JobRequest, current=Depends(admin)):
        row = resource(body.sop_id, "sop", current)
        jid = workflow.new_job(body.sop_id, body.objective, body.engine, current["id"])
        store.audit(current["id"], "factory.start", row["payload"]["name"])
        workflow.start(jid, row["payload"]["text"], body.objective, body.engine)
        return dict(id=jid, status="running")

    @app.get("/api/factory/jobs")
    def jobs(current=Depends(admin)):
        out = []
        for r in store.list_resources("factory_job", current):
            p = r["payload"]
            out.append(dict(id=r["id"], status=p["status"], sop_id=p["sop_id"], created=p["created"], totals=p.get("totals"), title=(p.get("spec_summary") or {}).get("title"), owner=r["owner"]))
        return out

    @app.get("/api/factory/jobs/{rid}")
    def job(rid: str, current=Depends(admin)):
        row = resource(rid, "factory_job", current)
        return dict(id=rid, **row["payload"])

    def review(rid, current, approve, comment):
        row = resource(rid, "factory_job", current)
        p = row["payload"]
        if p["status"] not in {"awaiting_approval"}:
            raise HTTPException(409, f"Job is {p['status']}; only jobs awaiting approval can be reviewed")
        sop_row = store.get(p["sop_id"], "sop")
        analysis = compiler.analyze(sop_row["payload"]["text"])
        report = checks.run_all(p["pack"], analysis)
        decision = checks.evaluate(checks.policy_input(report, analysis, p["pack"], trainer_approved=approve, reviewer=current["id"], author=row["owner"]))
        if approve and not decision["allow"]:
            raise HTTPException(422, dict(message="Policy gate denied publication", deny=decision["deny"]))
        draft = None
        if approve:
            draft = pack_draft(p["pack"], current["id"], "sop-factory", dict(factory_job=rid, approved_by=current["id"], review_comment=comment))
            with store.connection() as db:
                admins = [r[0] for r in db.execute("SELECT id FROM users WHERE role='admin'")]
            store.notify(admins, f"draft:{draft['id']}", "Scenario ready to publish", f"{draft['definition']['title']} passed {report['passed']}/{report['total']} checks and was approved by {current['name']}. Review it in Scenario studio.")
        p.update(status="approved" if approve else "rejected", policy=decision, review=dict(by=current["id"], comment=comment, at=time.time(), approved=approve), draft_id=draft["id"] if draft else None)
        for s in p["steps"]:
            if s["key"] == "approval":
                s.update(status="completed" if approve else "failed", detail=("Approved" if approve else "Rejected") + (f": {comment}" if comment else ""))
        if not store.update(rid, p, row["version"]):
            raise HTTPException(409, "Job changed; refresh and retry")
        store.audit(current["id"], "factory.approve" if approve else "factory.reject", rid)
        return dict(id=rid, **p)

    @app.post("/api/factory/jobs/{rid}/approve")
    def approve(rid: str, body: Review, current=Depends(admin)):
        return review(rid, current, True, body.comment)

    @app.post("/api/factory/jobs/{rid}/reject")
    def reject(rid: str, body: Review, current=Depends(admin)):
        return review(rid, current, False, body.comment)

    @app.get("/api/factory/jobs/{rid}/promptfoo")
    def promptfoo(rid: str, current=Depends(admin)):
        row = resource(rid, "factory_job", current)
        p = row["payload"]
        if not p.get("pack"):
            raise HTTPException(400, "The job has not produced a scenario yet")
        sop_row = store.get(p["sop_id"], "sop")
        analysis = compiler.analyze(sop_row["payload"]["text"])
        report = checks.run_all(p["pack"], analysis)
        tests = "\n".join(
            f"  - description: {json.dumps(c['name'])}\n    vars:\n      check: {json.dumps(c['name'])}\n    metadata:\n      category: {c['category']}\n    assert:\n      - type: javascript\n        value: \"JSON.parse(output).passed === true\""
            for c in report["tests"] + report["redteam"]
        )
        config = (
            f"# Promptfoo suite exported by SimForge for: {report['spec']['title']}\n"
            "# Run:  npx promptfoo@latest eval -c promptfooconfig.yaml   (set SIMFORGE_ROOT to the SimForge-AI folder)\n"
            "description: SimForge scenario checks and red-team suite\n"
            "providers:\n  - id: file://simforge_provider.py\n    label: simforge-scenario-harness\n"
            "prompts:\n  - '{{check}}'\n"
            f"tests:\n{tests}\n"
        )
        provider = (
            '"""Promptfoo Python provider: runs the SimForge check harness against the exported pack."""\n'
            "import json\nimport os\nimport sys\n\n"
            f"ROOT = os.environ.get('SIMFORGE_ROOT', {str(ROOT)!r})\n"
            "sys.path.insert(0, ROOT)\n"
            "from backend.factory import checks  # noqa: E402\n\n"
            "HERE = os.path.dirname(os.path.abspath(__file__))\n"
            "PACK = json.load(open(os.path.join(HERE, 'scenario_pack.json'), encoding='utf-8'))\n"
            "ANALYSIS = json.load(open(os.path.join(HERE, 'sop_analysis.json'), encoding='utf-8'))\n"
            "_REPORT = None\n\n\n"
            "def call_api(prompt, options, context):\n"
            "    global _REPORT\n"
            "    _REPORT = _REPORT or checks.run_all(PACK, ANALYSIS)\n"
            "    name = context['vars']['check']\n"
            "    found = next((c for c in _REPORT['tests'] + _REPORT['redteam'] if c['name'] == name), None)\n"
            "    return {'output': json.dumps(found or {'passed': False, 'detail': 'check not found'})}\n"
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("promptfooconfig.yaml", config)
            z.writestr("simforge_provider.py", provider)
            z.writestr("scenario_pack.json", json.dumps(p["pack"], indent=2))
            z.writestr("sop_analysis.json", json.dumps(analysis, indent=2))
            z.writestr("README.md", "# SimForge Promptfoo export\n\n```\nset SIMFORGE_ROOT=<path to SimForge-AI>\nnpx promptfoo@latest eval -c promptfooconfig.yaml\nnpx promptfoo@latest view\n```\n")
        return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="promptfoo-{rid}.zip"'})
