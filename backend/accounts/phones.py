import re

# +972 then area/mobile prefix 2-9, then 7-8 digits (landline 7, mobile 8)
_VALID = re.compile(r"^\+972[2-9]\d{7,8}$")


def normalize_il_phone(raw):
    """Normalize any Israeli phone spelling to E.164 (+972...). None if invalid."""
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", raw)
    if s.startswith("00972"):
        s = s[5:]
    elif s.startswith("+972"):
        s = s[4:]
    elif s.startswith("972"):
        s = s[3:]
    elif s.startswith("0"):
        s = s[1:]
    else:
        return None
    s = "+972" + s.lstrip("0")
    return s if _VALID.match(s) else None
