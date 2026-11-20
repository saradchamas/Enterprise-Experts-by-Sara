# Scanner output samples

- `npm-audit.json`, `pip-audit.json`: real output captured from the tools (npm audit on lodash 4.17.15 + minimist 1.2.0; pip-audit on jinja2 2.10).
- SARIF, osv-scanner, trivy and gitleaks samples are built inside `tests/test_universal.py` by hand, following each tool's documented format. They have not been checked against output captured from those tools.
