# Research and Innovation Workflow (Lite edition)

Use this when the user answered yes to `innovation_scan`, or asks what newer technology, AI model, tool or integration would help their project. With a "no", research only what a finding needs (see `improvement-loop.md`).

This is a workflow across existing experts, led by Technology Strategy (21) and Technical Leadership (22). It is not a list of what is fashionable. Its output is a short set of proposals, each tied to a problem this project has, each resting on pages you read during this review.

## Why memory is not enough here

Model line-ups, prices, library versions, MCP servers and hosting products change within months, and your own knowledge has a cutoff. A model you remember as the newest may be retired; a tool you remember may have a successor. So nothing is stated as current unless you read it on a page during this review.

If you cannot browse in this session, say so, record no sources, and give your suggestions under a heading that says they come from general knowledge with a cutoff and need checking.

## When to do it

Sources for findings are needed as you write each High or Critical finding, in every wave: look them up then. The wider scan below runs in the Synthesis wave, when all findings are known. If the user limited how many pages you may read, spend them first on Critical findings, then High, then the scan, and write "source not checked (limit reached)" where one is missing.

## Step 1 — Decide what to look for

Start from the project, not from the news:

- **Findings**: each High or Critical, and Medium findings where a tool or newer version is the natural fix.
- **Stated goals**: what the user said about where the product is going.
- **What the project runs on**: the version in use of each framework, runtime and major library against the current release and its end-of-support date.
- **Gaps in tooling**: checks that were not assessed because no tool was there.
- **AI in the product** (only if it has any): the models in use against what the provider now offers and has deprecated.
- **Integrations for the team's own work**: connectors and MCP servers for systems the user already uses. Follow `companion-skills.md` for vetting.

Write the list in `21-technology-strategy.md` before searching. Six to twelve questions is typical for a full review.

## Step 2 — Search, within the privacy answer

- `yes_generic_searches_only`: search for technologies and versions only. Do not put the project's name, client names, code, internal URLs or error text with identifiers into a search or a fetch.
- `yes_project_details_allowed`: you may also search for specific error messages and describe the use case. Secrets and personal data never go into a search.

Go to the primary source first: the vendor's or maintainer's own documentation, release notes, pricing page, registry entry or repository. Blogs and comparison sites are leads to follow, not sources to cite alone. Read the page itself; a search snippet is not a read page. If a page was blocked or reached only through a summarising tool, say so.

Record each page in `research-log.md` as a source, and in the evidence log as an observation:

| ID | Category | Subject | Official? | Read on | URL | What the page said |
|---|---|---|---|---|---|---|

Categories: technology, model, mcp, tool, dataset, practice. "Official" means the vendor's or maintainer's own page.

Look for the reasons not to adopt as hard as for the reasons to: open security advisories, a licence change, a maintainer who has left, breaking changes, lock-in, cost at ten times the current usage.

## Step 3 — Propose

A proposal is worth writing only when it beats leaving things as they are. Each proposal (`P-001`, …) in `research-log.md` has: the title; the area; the action (adopt, replace, upgrade, remove, configure); the finding IDs or the user's stated goal it serves; the source IDs; the alternatives considered; effort (S, M, L); risk; rollback; status.

Do not write a proposal that:

- names no finding and no stated goal (a solution looking for a problem),
- cites no recorded source,
- considered no alternative (keeping things as they are counts as one),
- is a model, MCP server, tool or dataset without at least one official source,
- rests only on sources for fast-moving facts that were read more than 90 days ago.

Put such an idea under "Not supported yet" with what is missing. Removing something is a legitimate proposal, often the best one. Say plainly which areas you looked at and found nothing worth changing.

## Step 4 — The user decides

Present the three to five proposals with the best ratio of benefit to effort and risk, then the rest in a table. Do not start on any of them. Record each decision with the user's name and the date: approved (with the files the change may touch, also written to `approvals.md`), rejected (with their reason), or deferred (with what it is waiting for). "Not now" is deferred, not rejected.

Installing a tool, adding an MCP server, creating an account, calling a paid model or sending data to a provider each need their own explicit yes.

## Step 5 — Build it and prove it

An approved proposal goes through the same loop as a fix (`improvement-loop.md`): a branch, a baseline first, the smallest change, the agreed check, review, rollback notes. Mark it *implemented* when the change is made and *verified* only when a check that ran after the approval passed; cite that evidence ID. If the measured result does not beat the baseline, revert and record the numbers. A new technology that made nothing measurably better is not an improvement.

## What goes in the final report

A section "Research and proposals": the questions asked, what was adopted and verified, what is waiting for a decision, what was rejected or deferred and why, what could not be checked, and the date the sources were read. State that the sources were recorded by the reviewer and that a reader should open a link before acting on a proposal.
