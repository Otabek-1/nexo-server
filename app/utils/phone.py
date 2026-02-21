import re

PHONE_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone_e164(value: str) -> str:
    raw = str(value or "").strip().replace(" ", "")
    if PHONE_E164_RE.match(raw):
        return raw
    return ""
