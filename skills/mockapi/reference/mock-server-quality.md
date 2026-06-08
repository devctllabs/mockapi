# Mock Server Quality Gate

Use this reference after `generate.py --run-codegen` and after completing
LLM-owned `src/features/**`, `src/controllers.ts`, seed data, adjacent feature
unit tests, and smoke tests. This is a final handoff gate, not a scaffold scope
probe. A freshly generated scaffold is expected to fail because operation
adapters start as TODOs and feature seed stubs start empty.

## Required Checks

Run the generated package typecheck first, then run the code-only quality
checker:

```bash
<python> <skill-root>/scripts/check_generated_quality.py --package-root <packageRoot>
```

Resolve `<python>` to Python 3.11+ before running bundled scripts. Fix every
quality error before handoff. Warnings should be fixed when obvious; otherwise
report them with the residual risk.

If the checker reports `quality.phase.incompleteImplementation`, continue
implementing behavior from `.mockapi/behavior.md` before treating the quality
results as final handoff status.

## ID Policy

Counter IDs are the default for create operations. When behavior says an
operation creates generated, sequential, prefixed, or counter-based IDs, the
profile must include the singleton `idCounters` state slice and feature code
should allocate IDs with `newIdAllocator`.

`validate_profile.py` warns when behavior describes generated/counter IDs
without `idCounters`. The quality checker errors when completed code uses
`newIdAllocator` but generated state still has no `idCounters`.

Do not infer slug IDs from OpenAPI examples or request names. Slug-style,
name-derived, or title-derived IDs are allowed only when the behavior sidecar
explicitly says they are required or intentionally confirmed product behavior.
The quality checker warns when slug helper code is present, but behavior policy
is validated by `validate_profile.py`.

## Architecture Signals

Keep state access feature-local. Use feature repositories for reads, writes,
and selectors over owned slices. Use `MockStateStore` directly only for
transactions, mock clock, ID counters, admin-like snapshot operations, or
cross-feature orchestration.

Every completed feature that owns non-infrastructure product state slices must
have `src/features/<feature>/repository.ts`. `idCounters` is infrastructure and
does not require a feature repository by itself. Feature services and operation
controllers must not call `getSlice`, `setSlice`, `findEntities`, `findEntity`,
`createEntity`, `updateEntity`, or `deleteEntity` on product state slices
directly; keep those calls inside feature repositories.

Repositories should expose named mutations and selectors. Feature services
should not perform whole-collection read-copy-overwrite flows such as
`const rows = repo.all(); repo.setAll([...rows, row])`; add `create`, `update`,
`markDeleted`, `restore`, `remove`, `addItem`, or a feature-specific selector
to the repository instead. Prefer `find` or `require` over `byId`; avoid
service-facing `setAll`, `setItems`, and `replaceAll` feature APIs.

Allocate IDs with one `newIdAllocator(stateStore.getSlice('idCounters'))` per
transaction and pass that allocator into helpers that need additional IDs. Do
not recreate allocators inside nested helpers in the same transaction.

Keep `src/lib` product-agnostic and close to infrastructure helpers from the
template: clone, errors, request context, IDs, soft delete, and sorting. Put
product/domain helpers inside the owning feature, for example
`src/features/notes/noteDetails.ts`, `src/features/settings/defaultSettings.ts`,
or `src/features/location-path/resolver.ts`. Avoid catch-all product modules
such as `src/lib/notes.ts`, `src/lib/deckStats.ts`, `src/lib/tree.ts`, or
`src/lib/domain.ts`.

Keep operation controllers thin. They should parse/normalize request inputs,
call dependencies, and return typed responses; they should not contain
repository-style data access. Use the generated operation data shape: path
parameters are `input.path`, not `input.params`.

Avoid `as any` in feature and controller code. If a generated runtime typing
gap forces a cast, keep it local and explain the gap.

## Seed Data

When `.mockapi/profile.toml` omits `state.seed` or sets it to `true`, completed
mock servers must populate product seed slices according to
`reference/seed-data.md`. Empty generated product stubs such as `workspaces: []`
are quality errors.

Set `state.seed = false` only when the requested mock server should start with
empty product data. Infrastructure state such as `idCounters` may remain empty
when appropriate.

The quality checker reports `quality.seed.emptyProductSeed` for empty product
seed literals while seed data is enabled.

## Test Coverage

Generated packages use Vitest. Keep HTTP smoke tests in `src/app.test.ts` by
default. Use `src/config.test.ts` only for config/env resolution. Add adjacent
unit tests for completed LLM-owned feature behavior:

- `src/features/<feature>/service.test.ts` for `service.ts`
- `src/features/<feature>/repository.test.ts` for `repository.ts`
- `src/features/<feature>/<helper>.test.ts` for feature-local helpers

Do not unit-test generated thin operation controller adapters by default. Add an
adjacent controller test only when the adapter performs non-trivial request
normalization or branching not covered by service or app smoke tests.

Before handoff, add `src/app.test.ts` coverage for:

- create operations returning counter IDs such as `workspace-1`
- custom `basePath` mounting
- admin state reset or state inspection when admin endpoints are generated
- one representative workflow per non-trivial feature

Run the generated package `test` script after typecheck and before
`check_generated_quality.py`.
