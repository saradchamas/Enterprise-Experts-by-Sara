# Diagrams, Screenshots and Visual Regression

Two different things, never mixed:

- **Evidence**: diagrams derived from the code, and screenshots captured from the running application.
- **Illustration**: target designs, annotated explanations, optional 3D or stylised presentation graphics.

An illustration is labelled Proposed or Illustration and is never presented as proof that a feature works. A mockup is not a screenshot.

## Diagrams

`EE graph <project> --out <review>/graphs` generates the module dependency graph and database ERD from the files (Observed). Draw the rest in Mermaid from what you inspected, and label each diagram:

| Label | Meaning |
|---|---|
| Verified | Confirmed by something that ran (for example a trace or a request log) |
| Observed | Derived from code or configuration you read |
| Inferred | Reasoned; say from what |
| Proposed | A target or recommended design, not the current system |

Useful diagrams, only where the project has the thing: system context and containers (C4), API and service interactions for the critical journeys (sequence), data flow with trust boundaries (for the threat model), deployment and infrastructure, state machines for key entities. Keep them readable: one idea per diagram, at most about fifteen nodes, real names from the code. After verified code changes, regenerate (`EE graph`) and update the affected diagrams.

Charts of measurements (benchmarks, scores over time) use only numbers that exist in the evidence.

## Real screenshots

Only when the capability matrix says `visual documentation: yes` and the interface can actually be run (intake `ui_run`, an allowed environment). No interface, or it cannot be run here: no screenshots, and UI checks that needed them are Not assessed.

1. Start the app locally or use the staging URL the user allowed. Use a test account with no real personal data.
2. Capture with a browser tool, through `EE evidence run` so the capture is recorded. With Playwright:
   `npx playwright screenshot --viewport-size=1440,900 --full-page <url> <review>/screenshots/raw/home-desktop.png`
   Cover what applies: desktop (1440×900), tablet (768×1024), mobile (390×844), dark mode (`--color-scheme=dark`), and RTL pages for Arabic interfaces.
3. Before saving anything that will be shared, make sure no personal data, tokens or keys are visible. Use seeded test data rather than editing the image.
4. Name captures `<page>-<viewport>[-dark][-rtl]`, lowercase with dashes.
5. Never edit, crop to mislead, or redraw a capture. Annotated copies (numbered callouts) are saved as separate files and described as annotated.

Mobile apps: use the platform's own tools (simulator or device screenshots) when available; otherwise Not assessed.

## Visual regression

`EE visual compare --review <review> --name home-desktop --image <png>` compares a capture with the approved baseline in `enterprise-review/visual-baselines/`.

- `no_baseline`: nothing has been approved yet. Show the capture to the user; if they confirm it is correct, `EE visual approve --review <review> --name home-desktop --by <their name>`. Only the user decides that a look is right.
- `match`: within the allowed difference (default 0.1% of pixels; small colour differences from antialiasing are ignored).
- `changed`: report it with both images. A change is not automatically a defect: if it was intended and the user approves, approve the new baseline; otherwise it is a finding for UI/UX (13).

After an approved UI fix, capture again, compare, and refresh the screenshots used in documentation so they match the code. Record baselines and captures with the commit they were taken from.
