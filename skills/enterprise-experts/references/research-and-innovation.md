# Research and Innovation Workflow

Use this when the intake answer to `innovation_scan` is a yes, or when the user asks what newer technology, AI model, tool or integration would help their project. With a "no", research only what a finding needs (see `improvement-loop.md`) and skip the rest of this file.

This is a workflow across existing experts, led by Technology Strategy (21) and Technical Leadership (22). It is not a 24th expert, and it is not a list of what is fashionable. Its output is a short set of proposals, each tied to a problem this project has, each resting on pages you read during this review.

## Why memory is not enough here

Model line-ups, prices, library versions, MCP servers and hosting products change within months, and your own knowledge has a cutoff. A model you remember as the newest may be retired; a tool you remember may have a successor; a server you remember may be abandoned. So in this workflow nothing is stated as current unless you read it on a page during this review. The engine enforces that: a proposal cannot be recorded without a dated source.

If you have no way to browse in this session, say so, record nothing as a source, and give your suggestions under a heading that says they are from general knowledge with a cutoff and need checking. Do not run `EE research add` for a page you did not open.

## Step 1 — Decide what to look for

Start from the project, not from the news. Build the list from:

- **Findings**: each High or Critical finding, and Medium findings where a tool or newer version is the natural fix.
- **Stated goals**: what the user said in the intake about where the product is going (scale, cost, new features, AI).
- **What the project runs on**: for each framework, runtime and major library in `discovery.json`, the version in use against the current release and its end-of-support date.
- **Gaps in tooling**: checks that were Not assessed because no tool was there (no scanner, no tests for the UI, no tracing).
- **AI in the product** (only if the capability matrix says so): the models in use against what the provider now offers and has deprecated.
- **Integrations for the team's own work**: connectors and MCP servers for systems the user already uses (their tracker, database, monitoring, design tool). Follow `companion-skills.md` for vetting.

Write the list down in `21-technology-strategy.md` before searching, so the search stays tied to it. Six to twelve questions is typical for a full review; three or four for a quick one.

## Step 2 — Search, within the privacy answer

- `yes_generic_searches_only`: search for technologies and versions only ("PostgreSQL 16 end of life", "FastAPI background tasks alternatives"). Do not put the project's name, client names, code, internal URLs or error text containing identifiers into a search or a fetch.
- `yes_project_details_allowed`: you may also search for specific error messages and describe the use case. Secrets and personal data never go into a search.

For each question:

1. Go to the primary source first: the vendor's or maintainer's own documentation, release notes, pricing page, registry entry or repository. Blogs, lists and comparison sites are leads to follow, not sources to cite alone.
2. Read the page itself. A search snippet is not a read page. If a page is blocked or only reachable through a summarising tool, say so in the claim.
3. Record what you read:

```
EE research add --review <review> --area 21 --category model \
  --subject "<provider> model line-up" --url <url> --official \
  --claim "<what the page said, in your words, including the version, date or price tier it applies to>"
```

Categories: `technology` (framework, runtime, library, database, platform), `model`, `mcp`, `tool`, `dataset`, `practice`. Use `--official` only for the vendor's or maintainer's own page. Use `--published` when the page shows its date. The source is also written to the evidence log as an observation.

Look for the reasons not to adopt as hard as for the reasons to: open security advisories, a licence change, a maintainer who has left, breaking changes between the project's version and the new one, lock-in, cost at 10× the current usage.

## Step 3 — Propose

A proposal is worth writing only when it beats leaving things as they are. For each one that does:

```
EE research propose --review <review> --area 6 --category technology --action-kind upgrade \
  --title "Upgrade PostgreSQL 12 to 16" --findings DB-003 --sources R-004 R-005 \
  --alternatives "stay on 12 with a paid support contract" "move to a managed service" \
  --effort M --risk "two extensions need new versions" --rollback "restore the pre-upgrade snapshot"
```

The engine refuses a proposal that:

- names no finding and no stated goal (a solution looking for a problem),
- cites no recorded source, or a source that does not exist,
- considered no alternative (keeping things as they are counts as one),
- is a model, MCP server, tool or dataset without at least one official source.

Give `--goal "<the user's words>"` when the proposal serves a goal and not a finding. `--action-kind` is one of adopt, replace, upgrade, remove, configure. Removing something is a legitimate proposal, often the best one.

Write each proposal up in the owning expert's deliverable using the recommendation fields in `improvement-loop.md` (problem, applicability to the versions in use, options, trade-offs, verification). Then:

```
EE research check --review <review>     # exit 0 when every proposal is supported
EE research log --review <review>       # writes research-log.md
```

`research-log.md` separates proposals that are supported from those that must not be acted on yet, and lists every source with the date it was read. Sources for fast-moving facts count for 90 days; after that the proposal is flagged until the page is read again.

Rank what you present: the three to five proposals with the best ratio of benefit to effort and risk, then the rest in a table. Say plainly which areas you looked at and found nothing worth changing. "The current choice is right; here is what I checked" is a useful result.

## Step 4 — The user decides

Present the proposals; do not start on any of them. For each the user accepts or declines:

```
EE research decide --review <review> --id P-001 --status approved --by "<their name>" --paths "db/*" "docker-compose.yml"
EE research decide --review <review> --id P-002 --status rejected --reason "<why, in their words>"
```

Approval with `--paths` also records the approval the edit guard checks, so the change can touch those files and no others. Installing a tool, adding an MCP server, creating an account, calling a paid model or sending data to a provider each need their own explicit yes; an approved proposal does not imply them.

## Step 5 — Build it and prove it

An approved proposal is implemented through the same loop as a fix (`improvement-loop.md`): open remediation, work on a branch, baseline first, the smallest change, tests and the agreed check through `EE evidence run`, independent review, rollback notes.

```
EE research decide --review <review> --id P-001 --status implemented
EE research decide --review <review> --id P-001 --status verified --evidence E-0NN
```

`verified` is accepted only when `E-0NN` is a command that ran and exited 0 after the approval. A proposal that was built but whose check failed stays `implemented`, and the report says so. If the measured result does not beat the baseline, revert and record it as rejected with the numbers as the reason. A new technology that made nothing measurably better is not an improvement.

## What goes in the final report

A section "Research and proposals" with: the questions asked, what was adopted and verified, what was proposed and is waiting for a decision, what was rejected and why, what could not be checked (blocked pages, no browsing), and the date the sources were read. `EE package` copies `research-log.md` and `research.json` into the delivery folder and notes any proposal that is not supported.
