# Scenario demo briefs

Use this folder for reusable, human-readable scenario briefs and reference documents for Scenario Lab demos. It complements `samples/sops/`, which contains procedure-oriented examples.

These Markdown files are reference material, not executable scenario packs. To use one in the app, open **Scenario Lab**, describe the learning mission, optionally upload the brief as a reference, generate a draft, and review the mission, actions, and validation results before publishing. The supported upload formats and limits are in the root `README.md`.

- Start from [`scenario-brief-template.md`](scenario-brief-template.md) for a new domain.
- Use [`warehouse-cold-chain-disruption.md`](warehouse-cold-chain-disruption.md) as a synthetic example prompt.
- For version-controlled YAML packs, follow [`../../docs/ADDING_USE_CASES.md`](../../docs/ADDING_USE_CASES.md) and use `scripts/scenario_kit.py` to validate and test the pack.

Keep briefs focused and useful: define a real operational problem, learner, systems, hidden incident, observable evidence, plausible decoys, consequential actions, measurable outcomes, and a short demo path. Use synthetic data only. Do not include credentials, real personal/customer information, instructions to execute code, or directives to bypass human review. Uploaded documents are untrusted references; review extracted text and generated drafts.

The existing `samples/sops/supplier_disruption_sop.md` contains personal-looking metadata and instruction-like text that asks to bypass review and delete records. Treat it as untrusted-input material, not as a clean source document for a demo upload.
