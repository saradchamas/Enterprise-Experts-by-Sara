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
     re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:/@'\"]+:((?!\$\{|\$[A-Z_]|\{\{|%\(|<)[^\s@'\"]{3,})@")),
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


# Broader patterns used only when masking captured output. They would be too noisy for
# reporting findings, but when in doubt about a value in a log, hiding it is the safe side.
MASK_EXTRA = [
    re.compile(r"(?i)\b(?:bearer|basic|token)\s+([A-Za-z0-9._~+/=\-]{16,})"),
    re.compile(r"(?i)[?&](?:token|key|api_?key|access_token|secret|password|sig|signature)=([^&\s'\"]{6,})"),
    re.compile(r"(?i)[\"']?\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?key|access[_-]?token|auth[_-]?token|"
               r"client[_-]?secret|private[_-]?key)\b[\"']?\s*[:=]\s*[\"']?([^\s\"',;}{]{6,})"),
    re.compile(r"(?i)--?(?:password|passwd|token|secret|api-key)[ =]([^\s]{6,})"),
    re.compile(r"\b(?:xox[baprs]|glpat|ghs|github_pat|npm|pypi|sk_test|rk_test|whsec|shpat|SG)[-_][A-Za-z0-9._\-]{12,}"),
    re.compile(r"(?s)(-----BEGIN [A-Z ]*PRIVATE KEY-----)(.+?)(-----END)"),
]


def mask_text(text):
    """Mask anything that looks like a secret so evidence files never store one."""
    def repl(m):
        secret = m.group(m.lastindex) if m.lastindex else m.group(0)
        return m.group(0).replace(secret, mask(secret))
    text = MASK_EXTRA[-1].sub(lambda m: m.group(1) + "…masked…" + m.group(3), text)   # key bodies first
    for _label, rx in SECRET_PATTERNS:
        if _label != "Private key block":
            text = rx.sub(repl, text)
    text = ENV_SECRET.sub(repl, text)
    for rx in MASK_EXTRA[:-1]:
        text = rx.sub(repl, text)
    return text
