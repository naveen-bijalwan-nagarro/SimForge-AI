"""Reviewed admin upload packet. Loading creates references, never drafts or publications."""

import base64

from fastapi import HTTPException

from . import scenario_sources, settings

KEYS = ("factorypulse_machine_failure",)
DIRECTORY = settings.ROOT / "samples" / "sample1"
REFERENCE_FILES = (
    "FactoryPulse_Operations_Brief.docx",
    "FactoryPulse_Sensor_Charts.pdf",
)


def catalogue():
    return [dict(id=key, title="FactoryPulse — Machine Failure") for key in KEYS]


def load(key, owner):
    if key not in KEYS:
        raise HTTPException(404, "Demo example not found")
    files = []
    for name in REFERENCE_FILES:
        path = DIRECTORY / name
        files.append(dict(name=name, content=base64.b64encode(path.read_bytes()).decode()))
    result = scenario_sources.upload(scenario_sources.Upload(files=files), owner)
    return dict(**result, prompt=(DIRECTORY / "admin_prompt.txt").read_text(encoding="utf-8"))
