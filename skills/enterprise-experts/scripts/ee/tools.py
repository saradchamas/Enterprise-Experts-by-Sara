"""Optional analysis tools the experts can use when they are installed.

Nothing here is required. A tool that is not installed means its check is Not
assessed; the engine never substitutes a guess. Commands are run through
`evidence run`, which keeps the raw output, tool version, time and exit status.
"""
import shutil

TOOLS = [
    # name, areas, purpose, example command, licence note
    ("semgrep", [2, 22], "static security and bug patterns", ["semgrep", "scan", "--config", "auto", "--error"], "open source CLI; some rule packs need an account"),
    ("osv-scanner", [2], "known vulnerabilities in dependencies", ["osv-scanner", "scan", "-r", "."], "open source"),
    ("trivy", [2, 10, 11], "vulnerabilities and misconfiguration in files, images and IaC", ["trivy", "fs", "."], "open source"),
    ("gitleaks", [2], "secrets in files and git history", ["gitleaks", "detect", "--redact", "--no-banner"], "open source"),
    ("codeql", [2], "deep code scanning", ["codeql", "version"], "free for open source; licence needed for private code"),
    ("scorecard", [2, 10], "OpenSSF supply-chain posture of a repository", ["scorecard", "--repo", "<repo-url>"], "open source; needs a GitHub token"),
    ("sonar-scanner", [22], "code quality and debt", ["sonar-scanner"], "needs a SonarQube server or SonarCloud account"),
    ("hadolint", [10], "Dockerfile lint", ["hadolint", "Dockerfile"], "open source"),
    ("tflint", [11], "Terraform lint", ["tflint"], "open source"),
    ("checkov", [11], "IaC policy checks", ["checkov", "-d", "."], "open source"),
    ("k6", [3, 4], "load tests with pass/fail thresholds", ["k6", "run", "<script.js>"], "open source; local or staging targets only"),
    ("lighthouse", [3, 13], "web performance and accessibility", ["lighthouse", "<url>", "--output=json", "--quiet"], "open source; needs Chrome"),
    ("playwright", [9, 13], "end-to-end browser tests", ["npx", "playwright", "test"], "open source; needs browsers installed"),
    ("pa11y", [13], "accessibility checks", ["pa11y", "<url>"], "open source"),
    ("syft", [2, 10], "SBOM generation", ["syft", "dir:.", "-o", "cyclonedx-json"], "open source"),
]


def available():
    return [{"tool": name, "installed": shutil.which(name) is not None, "areas": areas, "purpose": purpose,
             "example": example, "licence": licence} for name, areas, purpose, example, licence in TOOLS]
