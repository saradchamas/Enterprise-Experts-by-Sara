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
2. Capture with a browser tool, through `EE evidence run` with `--output` naming the image, so the image itself becomes part of the record (a capture that fails, or an image edited afterwards, makes the record unusable):
   `EE evidence run --review <review> --area 13 --title "home, desktop" --project <project> --output <review>/screenshots/raw/home-desktop.png -- npx --no-install playwright screenshot --viewport-size=1440,900 <url> <review>/screenshots/raw/home-desktop.png`
   - Use `--no-install` so nothing is downloaded. If the browser is missing, the check is Not assessed.
   - Desktop: `--viewport-size=1440,900`. Tablet: `--viewport-size=768,1024`.
   - Phone: emulate a real device, `-b chromium --device="Pixel 7"`. A narrow viewport alone does not behave like a phone browser and will hide problems such as a missing viewport meta tag. iPhone profiles need WebKit to be installed.
   - Take both a viewport capture (what the user sees first) and, where the page is long, a `--full-page` one. If the full-page image is wider than the viewport, the page overflows: that is a finding.
   - Dark mode: `--color-scheme=dark`. Arabic and other right-to-left pages: capture them as their own pages.
   - A screenshot shows how a page looks in one state. It cannot show that a journey works. To verify a journey (type, click, check the result), write a small Playwright script in `<review>/probes/`, run it through `EE evidence run`, and have it save state captures as it goes. Measurements such as contrast ratios and touch-target sizes can be computed in the same script from the page's computed styles when no accessibility scanner is installed.
3. Before saving anything that will be shared, make sure no personal data, tokens or keys are visible. Use seeded test data rather than editing the image.
4. Name captures `<page>-<desktop|tablet|mobile|device>[-dark][-<state>]`, lowercase with dashes, for example `checkout-pixel7-after-submit`. A right-to-left page is its own page name (`home-ar-mobile`).
5. Never edit, crop to mislead, or redraw a capture. Annotated copies (numbered callouts) are saved as separate files and described as annotated.

Mobile apps: use the platform's own tools (simulator or device screenshots) when available; otherwise Not assessed.

## Visual regression

`EE visual compare --review <review> --name home-desktop --image <png>` compares a capture with the approved baseline. Baselines are kept in `enterprise-review/visual-baselines/`, beside the dated review folders, so the next review compares against them (`--baselines <dir>` puts them elsewhere). Every comparison is stored as its own evidence record, which the command prints, so a finding or check can cite the verdict. Only compare captures of the project itself; `compare` keeps the image you give it as that page's current capture.

- `no_baseline`: nothing has been approved yet. Show the capture to the user; if they confirm it is correct, `EE visual approve --review <review> --name home-desktop --by <their name>`. Only the user decides that a look is right.
- `match`: within the allowed difference (default 0.1% of pixels; small colour differences from antialiasing are ignored).
- `changed`: a difference image is written to `screenshots/<name>.diff.png` (changed pixels in red). Report it with the baseline, the new capture and the difference image. A change is not automatically a defect: if it was intended and the user approves, approve the new baseline; otherwise it is a finding for UI/UX (13).

After an approved UI fix, capture again, compare, and refresh the screenshots used in documentation so they match the code. Record baselines and captures with the commit they were taken from.
