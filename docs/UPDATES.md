# Versioning, Updates and Rollback

## Versioning

[Semantic Versioning](https://semver.org). Before 1.0.0, a minor version may change the review file formats; such changes are listed under "Breaking" in the [changelog](../CHANGELOG.md). `findings.json` carries a `schema_version`; the engine rejects versions it does not understand instead of guessing.

There is no automatic updater, by design: the tool should not change itself in the middle of reviewing a sensitive project. Updates are explicit.

## Check your version

```bash
python skills/enterprise-experts/scripts/enterprise_experts.py --version
```

Compare with the latest entry in the changelog or the GitHub releases page.

## Update

Plugin:

```bash
claude plugin marketplace update enterprise-experts-by-sara
claude plugin update enterprise-experts@enterprise-experts-by-sara
```

Standalone skill: replace the `enterprise-experts` folder with the new version's.

Clone: `git fetch --tags && git checkout vX.Y.Z`, then run the tests.

Before updating, read the changelog's "Breaking" section. Finish or archive reviews in progress first: a review folder is tied to the schema version that created it.

## Roll back

Plugin or clone: check out the previous tag (`git checkout vX.Y.Z`) and reinstall from that clone as described in [INSTALLATION.md](INSTALLATION.md). Standalone skill: restore the previous folder.

Review folders in your projects are never touched by an update or a rollback.

## Releases

Pushing a tag `vX.Y.Z` that matches the version in the code runs `.github/workflows/release.yml`: tests, a reproducible build of `enterprise-experts.skill`, an SBOM (`sbom.cdx.json`), `SHA256SUMS`, a build provenance attestation, and a GitHub release with the changelog entry. To check a download:

```bash
sha256sum -c SHA256SUMS
gh attestation verify enterprise-experts.skill --repo saradchamas/Enterprise-Experts-by-Sara
```

A signed release shows where the file came from and that it was not altered. It does not show that the software is free of defects.

## Tested

`tools/upgrade_rollback_test.sh <old> <new>` installs the old version of the plugin from a local clone, upgrades it, and rolls back by uninstalling and installing the earlier version. It passed for 0.3.0 → 0.4.0 → 0.3.0 (Linux, Claude Code CLI). Note that `claude plugin update` only moves forward; rolling back is uninstall, then install.

## What is not done yet

- No release has been tagged, so the release workflow has not run and the verification commands above are untested.
- No migration tool converts an older review folder to a newer schema; re-run the review.
