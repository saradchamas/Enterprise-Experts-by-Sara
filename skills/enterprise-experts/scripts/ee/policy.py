"""Command policy for evidence collection.

This is a guardrail, not a sandbox: it refuses commands that are obviously
destructive, publish something, or change live systems, unless the caller states
that the user approved them. Real isolation comes from running in the Docker
runner (read-only project mount, no network) and from the user's own permissions.
"""
import re

_RULES = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rf]", "deletes files"),
    (r"\bgit\s+(push|reset\s+--hard|clean\b|checkout\s+--\s|rebase|commit|merge)\b", "changes git history or the remote"),
    (r"\b(terraform|tofu|pulumi)\s+(apply|destroy|up|import)\b", "changes live infrastructure"),
    (r"\bkubectl\s+(apply|delete|patch|scale|rollout|replace|drain|exec)\b", "changes a live cluster"),
    (r"\bhelm\s+(install|upgrade|uninstall|rollback)\b", "changes a live cluster"),
    (r"\b(docker|podman)\s+(push|system\s+prune|rm\b|rmi\b|volume\s+rm)", "publishes or deletes containers/images"),
    (r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bgem\s+push\b", "publishes a package"),
    (r"\b(vercel|netlify|firebase|flyctl|fly|heroku|wrangler|serverless|sls|eb|gcloud|az|aws)\b.*\b(deploy|publish|delete|destroy|rm|terminate|put-|create-|update-)", "deploys or changes cloud resources"),
    (r"(?i)\b(drop|truncate)\s+(table|database|schema)\b|\bdelete\s+from\b", "destructive SQL"),
    (r"\b(prisma\s+migrate\s+(deploy|reset)|prisma\s+db\s+push|alembic\s+upgrade|migrate\s+up|db:migrate|artisan\s+migrate)\b", "applies a database migration"),
    (r"\b(shutdown|reboot|mkfs|dd\s+if=)\b|\bchmod\s+-R\b|\bchown\s+-R\b", "system-level change"),
    (r"\bcurl\b.*\s-X\s*(POST|PUT|DELETE|PATCH)\b|\bcurl\b.*\s(-d|--data)\b", "sends a write request to a remote service"),
]
READ_ONLY = {"grep", "egrep", "fgrep", "rg", "cat", "head", "tail", "wc", "ls"}
_COMPILED = [(re.compile(rx), why) for rx, why in _RULES]


def check_command(argv):
    """Return None when the command is allowed, otherwise the reason it needs approval."""
    if argv and argv[0] in READ_ONLY:   # a search pattern may legitimately contain words like "delete from"
        return None
    text = " ".join(argv)
    for rx, why in _COMPILED:
        if rx.search(text):
            return why
    return None
