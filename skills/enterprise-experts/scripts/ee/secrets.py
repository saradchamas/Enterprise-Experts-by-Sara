"""Secret patterns shared by discovery (detection) and evidence capture (masking)."""
import re

SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{16,}\b")),
    ("Generic sk- API key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("Connection string with password",
     re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:/@'\"]+:([^\s@'\"]{3,})@")),
    ("Hardcoded credential assignment", re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key)\b"
        r"\s*[:=]\s*['\"]([^'\"\s$<{]{8,})['\"]")),
]
ENV_SECRET = re.compile(
    r"\b([A-Z0-9_]*(?:SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*=\s*([^\s'\"]{8,})")
PLACEHOLDER = re.compile(
    r"(?i)(example|changeme|change_me|your[_-]|placeholder|xxxx|dummy|test|sample|<.*>|\*\*\*|todo|localhost|password123?$)")


def mask(value):
    value = value.strip()
    return (value[:4] + "…" + value[-2:]) if len(value) > 10 else "…masked…"


def mask_text(text):
    """Mask anything that looks like a secret so evidence files never store one."""
    def repl(m):
        secret = m.group(m.lastindex) if m.lastindex else m.group(0)
        return m.group(0).replace(secret, mask(secret))
    for _label, rx in SECRET_PATTERNS:
        text = rx.sub(repl, text)
    return ENV_SECRET.sub(repl, text)
