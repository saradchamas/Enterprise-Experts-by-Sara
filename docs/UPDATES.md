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

## What is not done yet

- No tagged releases exist yet; v0.2.0 is the first version intended to be tagged, after its pull request is merged.
- The plugin update commands above follow the Claude Code CLI but have not been exercised against a published second version.
- No migration tool converts a schema-1 review to schema 2; re-run the review.
