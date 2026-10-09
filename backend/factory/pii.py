"""PII sanitization before any SOP text reaches storage, retrieval or an AI model.

Built-in recognizers always run. When Microsoft Presidio (``presidio-analyzer`` with a spaCy
model) is installed, its findings are merged in. Only the sanitized text is stored; findings
report entity types and counts, never the original values.
"""

import re

try:  # Optional: pip install presidio-analyzer presidio-anonymizer && python -m spacy download en_core_web_sm
    from presidio_analyzer import AnalyzerEngine

    _PRESIDIO = AnalyzerEngine()
    ENGINE = "Presidio + built-in recognizers"
except Exception:  # noqa: BLE001 - any import/model error falls back to built-in recognizers
    _PRESIDIO = None
    ENGINE = "Built-in recognizers (Presidio optional)"

TITLES = r"(?:Customer|Client|Employee|Owner|Contact|Manager|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Name:|Approved by|Prepared by|Reported by|Assigned to|Patient)"
# Capitalised words that follow a title but describe a role, not a person ("Customer Service Lead").
ROLE_TERMS = {
    "service", "services", "lead", "manager", "analyst", "team", "support", "success", "care",
    "communication", "communications", "planner", "controller", "coordinator", "officer",
    "director", "portal", "data", "account", "operations", "relations", "experience", "desk",
    "chain", "supply", "engineer", "agent", "representative", "owner", "review", "board",
}
RESERVED_DOMAIN = re.compile(r"(?i)@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|[\w-]+\.example|[\w-]+\.invalid|[\w-]+\.test)$")
PATTERNS = [
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("IBAN_CODE", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE_NUMBER", re.compile(r"(?<![\w/.-])\+?\(?\d{1,4}\)?(?:[\s.-]\(?\d{1,4}\)?){2,5}(?![\w/])")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("ACCOUNT_NUMBER", re.compile(r"(?i)\b(?:account|acct|a/c|iban|policy|member)\s*(?:no\.?|number|#)?\s*[:#]?\s*(\d[\d-]{5,20})")),
    ("DATE_OF_BIRTH", re.compile(r"(?i)\b(?:dob|date of birth|born)\s*[:]?\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")),
]


def _luhn(digits):
    digits = [int(d) for d in digits if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
    return total % 10 == 0


def find(text, allow_reserved=False):
    spans = []
    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text):
            start, end = (m.start(1), m.end(1)) if kind == "ACCOUNT_NUMBER" else (m.start(), m.end())
            value = text[start:end]
            if kind == "CREDIT_CARD" and not _luhn(value):
                continue
            if kind == "PHONE_NUMBER" and sum(c.isdigit() for c in value) < 9:
                continue
            if allow_reserved and kind == "EMAIL_ADDRESS" and RESERVED_DOMAIN.search(value):
                continue  # RFC 2606 reserved domains are synthetic, never personal data
            spans.append((start, end, kind))
    # Titles followed by a name also cover "Customer Naveen Bijalwan" style mentions.
    for m in re.finditer(rf"\b{TITLES}\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+){{1,2}})", text):
        if not any(w.lower() in ROLE_TERMS for w in m.group(1).split()):
            spans.append((m.start(1), m.end(1), "PERSON"))
    if _PRESIDIO is not None:
        try:
            for r in _PRESIDIO.analyze(text=text, language="en"):
                if r.score >= 0.5:
                    spans.append((r.start, r.end, r.entity_type))
        except Exception:  # noqa: BLE001 - Presidio failures never block sanitization
            pass
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    merged = []
    for s in spans:
        if merged and s[0] < merged[-1][1]:
            continue
        merged.append(s)
    return merged


def sanitize(text):
    """Replace detected entities with <TYPE> tokens. Returns (clean_text, findings summary)."""
    spans = find(text)
    out, last, counts = [], 0, {}
    for start, end, kind in spans:
        out.append(text[last:start])
        out.append(f"<{kind}>")
        counts[kind] = counts.get(kind, 0) + 1
        last = end
    out.append(text[last:])
    return "".join(out), dict(engine=ENGINE, entities=counts, total=sum(counts.values()))


def residual(text):
    """Entities still present (used by red-team checks after generation)."""
    return [dict(type=k, start=s, end=e) for s, e, k in find(text, allow_reserved=True)]
