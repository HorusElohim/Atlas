# Flutter peer-card redesign reference

## Validated pattern

For a dense live-peer section that previously rendered terminal-like full-width rows:

- Keep verified collaborators as a separate chip-based section.
- Render anonymous swarm observations as bounded cards.
- Card header: status dot, self-reported client name (or `Unknown client`), address, and an optional `LIVE` badge.
- Card body: a two-by-two metric grid:
  - `DOWNLOADED` — cumulative bytes fetched from that peer
  - `UPLOADED` — cumulative bytes sent to that peer
  - `DOWN SPEED` — current measured receive rate
  - `UP SPEED` — current measured send rate
- Use the project's canonical byte and rate formatters.
- Apply strong accent/glow only to a nonzero-rate peer; retain quiet connected peers without presenting them as active.
- Label the client as self-reported when it is shown; it is not verified identity data.
- Sort cards by current transfer activity, then cumulative exchanged bytes, when those values are already present in the domain model.

## Test contract

A focused widget test should render a realistic peer and assert the visible contract rather than private layout details:

- client name and address are visible;
- all four metric labels are visible;
- canonical total and speed values are visible;
- active state is represented by `LIVE`;
- a separate idle peer remains visible without an idle-as-active claim;
- verified/contact badges are not assigned to anonymous swarm peers;
- the card remains usable at a phone-sized width.

If an existing test checks the old row's exact color or tree shape, replace that assertion with the new product behavior. Preserve tests for trust boundaries and active/idle semantics.

## Verification record

The pattern was implemented in Portalis collection details and verified with:

- focused collection widget tests: 16 passed;
- full Flutter suite: 147 passed;
- `flutter analyze`: no issues;
- `git diff --check`: clean;
- coordinated frontend/backend version consistency test: passed;
- no leftover Flutter, Dart, Cargo, or rustc processes after the checks.
