"""Command policy for evidence collection.

This is a guardrail, not a sandbox: it refuses commands that are obviously
destructive, publish something, or change live systems, unless the caller states
that the user approved them. Real isolation comes from running in the Docker
runner (read-only project mount, no network) and from the user's own permissions.
"""
import re

_GIT = r"\bgit\b(?:\s+-{1,2}\S+(?:[ =]\S+)?)*?\s+"
_RULES = [
    (r"(?:^|\s)(rm|rmdir|unlink|shred)(\s|$)", "deletes files"),
    (r"\bxargs\b.*\b(rm|mv|cp|chmod|chown|git|sh|bash|sed)\b", "runs a changing command on a list of files"),
    (r"(?:^|\s)mv\s+\S+\s+\S|\bsed\s+(-\w*i|--in-place)|\btruncate\s", "moves or edits files in place"),
    # Copying INTO the review folder or a temp folder is how evidence is gathered; anywhere else overwrites.
    (r"(?:^|\s)cp\s+(?!.*\s\S*(?:enterprise-review|/tmp/)\S*\s*$)\S+\s+\S", "copies over files outside the review folder"),
    (r"\bfind\b.*\s-(delete|exec|execdir|ok)\b", "deletes or runs commands on files it finds"),
    (_GIT + r"(push|reset\s+--hard|clean\b|checkout\s+--\s|rebase|commit|merge|tag\s+-d|branch\s+-D|filter-branch|gc\b)",
     "changes git history or the remote"),
    (r"\bgh\s+(release|repo\s+(delete|create|edit)|pr\s+(merge|create|close)|workflow\s+run|secret|api\b.*(-X|--method))",
     "publishes or changes things on the repository host"),
    (r"\b(terraform|tofu|pulumi)\s+(apply|destroy|up|import)\b", "changes live infrastructure"),
    (r"\bkubectl\s+(apply|delete|patch|scale|rollout|replace|drain|exec)\b", "changes a live cluster"),
    (r"\bhelm\s+(install|upgrade|uninstall|rollback)\b", "changes a live cluster"),
    (r"\b(docker|podman)\s+(push|system\s+prune|rm\b|rmi\b|volume\s+rm)", "publishes or deletes containers/images"),
    (r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bgem\s+push\b", "publishes a package"),
    (r"\b(vercel|netlify|firebase|flyctl|fly|heroku|wrangler|serverless|sls|eb|gcloud|az|aws)\b.*\b(deploy|publish|delete|destroy|rm|terminate|put-|create-|update-)", "deploys or changes cloud resources"),
    (r"(?i)\b(drop|truncate)\s+(table|database|schema)\b|\bdelete\s+from\b", "destructive SQL"),
    (r"\b(prisma\s+migrate\s+(deploy|reset)|prisma\s+db\s+push|alembic\s+upgrade|migrate\s+up|db:migrate|artisan\s+migrate)\b", "applies a database migration"),
    (r"\b(shutdown|reboot|mkfs|dd\s+if=)\b|\bchmod\s+-R\b|\bchown\s+-R\b", "system-level change"),
    (r"\b(curl|wget|http)\b.*(\s-X\s*|--request[ =])(POST|PUT|DELETE|PATCH)\b|\bcurl\b.*\s(-d|--data\S*|-F|--form|-T|--upload-file)\b|\bwget\b.*--post",
     "sends a write request to a remote service"),
]
READ_ONLY = {"grep", "egrep", "fgrep", "rg", "cat", "head", "tail", "wc", "ls"}
SHELL_META = re.compile(r"[;&|`\n]|\$\(|>")
_COMPILED = [(re.compile(rx), why) for rx, why in _RULES]


def split_shell(command):
    """The separate commands inside one shell line (a rough split, good enough to check each part)."""
    return [part.strip() for part in re.split(r"&&|\|\||[;|\n]|\$\(|`", command) if part.strip()]


def check_command(argv):
    """For a command run WITHOUT a shell (as `evidence run` does): None when allowed, otherwise the
    reason it needs approval. Arguments are literal here, so a search tool is always read-only and
    its pattern may contain words like "delete from"."""
    if argv and argv[0] in READ_ONLY:
        return None
    text = " ".join(argv)
    for rx, why in _COMPILED:
        if rx.search(text):
            return why
    return None


_REDIRECT = re.compile(r"(?:\d?>>?|\btee\s+(?:-a\s+)?)\s*([^\s&|;<>]+)")
_SAFE_TARGET = re.compile(r"^(?:/dev/null|/tmp/|\$TMPDIR|&\d)|enterprise-review")


def check_shell(command):
    """For a shell line (as the Bash tool runs): every chained command is checked on its own, so
    `ls && rm -rf src` is judged by its second half, and writing files by redirection is caught."""
    for part in split_shell(command):
        reason = check_command(part.split())
        if reason:
            return reason
    for target in _REDIRECT.findall(command):
        if not _SAFE_TARGET.search(target):
            return f"writes a file through the shell ({target})"
    return None
