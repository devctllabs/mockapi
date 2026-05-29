# Seed Data

Seed data defines the generated mock server's initial product state. The Python
generator may create empty feature seed stubs, but completed mock servers should
not keep product state empty unless the profile explicitly requests it.

## Profile Policy

`state.seed` controls whether product seed data is expected:

```toml
[state]
schemaVersion = 1
seed = true
```

- Missing `state.seed` means `seed = true`.
- `seed = true`: populate deterministic product/business seed records before
  handoff.
- `seed = false`: empty product seed records are intentional.

`seed = false` does not disable `seedState()`, schema version, mock clock, or
infrastructure state such as `idCounters`.

## Ownership

Keep seed records in `src/features/<feature>/seed.ts`, next to the feature that
owns the slices through `features[].stateSlices`.

Do not put product seed records in
`src/generated/mock-admin/state/seed.ts`; that generated file creates the
shared `SeedContext`, initializes global state, and spreads feature seed
functions.

## Default Dataset

When `state.seed` is missing or true, replace empty generated product stubs such
as `workspaces: []` with a small coherent dataset:

- Use stable, readable IDs such as `workspace-1`, `deck-1`, and `note-1`.
- Create enough records to exercise list/detail/create/update flows, usually
  one to three records per primary slice.
- Keep cross-slice references valid, for example notes reference seeded decks
  and decks reference seeded workspaces.
- Use `SeedContext` for dates and mock-clock-relative values.
- Keep `idCounters` above the IDs already present in seed records when counter
  IDs are used.
- Avoid random data, faker libraries, current wall-clock dates, and real PII.
- Prefer product-realistic names over placeholder names such as `foo` or
  `test`.

Example:

```ts
import type { SeedContext } from '../../generated/mock-admin/state/seed.ts'
import type { MockState } from '../../generated/mock-admin/contract/index.ts'

type WorkspaceRecord = MockState['workspaces'][number]
type DeckRecord = MockState['decks'][number]

export const seedWorkspaces = ({ fromSeedNow }: SeedContext): Pick<MockState, 'workspaces' | 'decks'> => ({
  workspaces: [
    {
      id: 'workspace-1',
      title: 'Default Workspace',
      updatedAt: fromSeedNow(-2),
    } satisfies WorkspaceRecord,
  ],
  decks: [
    {
      id: 'deck-1',
      workspaceId: 'workspace-1',
      title: 'Getting Started',
      updatedAt: fromSeedNow(-1),
    } satisfies DeckRecord,
  ],
})
```

## Empty Seed

Use empty product seed only when the user explicitly asks for an empty initial
mock state. Record that choice in `.mockapi/profile.toml`:

```toml
[state]
schemaVersion = 1
seed = false
```

With `seed = false`, keep generated product stubs empty if that best matches
the requested mock server. Still initialize required singleton/infrastructure
state to valid defaults.

## Quality Gate

`check_generated_quality.py` reports `quality.seed.emptyProductSeed` when
`state.seed` is missing or true and feature seed files leave product slices as
empty array or empty object literals.

The checker is intentionally a static guard against abandoned generated stubs.
It does not prove that seed data is complete or product-correct; the LLM-owned
implementation remains responsible for coherent domain data.
