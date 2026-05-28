# Mock Server Structure

Generated mock servers are feature-first TypeScript/Hono packages. Keep behavior
near the feature that owns it; do not create a catch-all shared repository.
For compact implementation examples, read `reference/mock-server-examples.md`.

## Canonical Layout

```text
src/
  app.ts
  controllers.ts
  features/
    <feature>/
      service.ts
      repository.ts
      seed.ts
      controllers/<operationId>.ts
  generated/
    mock-admin/state/
      controller.ts
      repository.ts
      seed.ts
      service.ts
  lib/
```

`src/lib` is for product-agnostic infrastructure helpers only. Keep generated
template-style utilities there, such as clone, errors, request context, IDs,
soft delete, and sorting. Product/domain helpers belong under
`src/features/<feature>/...`; for cross-feature derived behavior, create a
small named feature service or resolver rather than a broad `src/lib/tree.ts`
or `src/lib/domain.ts`.

`src/generated/mock-admin/state/repository.ts` is the low-level in-memory state
store. It owns snapshot persistence, reset, clock helpers, transactions, and
typed `getSlice` / `setSlice` access.

`src/controllers.ts` is the composition root. Instantiate feature repositories
there from the shared `MockStateRepository`, add them to `MockApiDependencies`,
and pass `deps` into operation controller and service factories.

`src/generated/mock-admin/state/**` is generated admin infrastructure. Do not
edit those files by hand; use feature modules for behavior and feature seed
files for seed data.

## Features

Each stateful domain feature owns its local domain access:

- `src/features/<feature>/service.ts`: feature behavior and orchestration from
  `.mockapi/behavior.md`.
- `src/features/<feature>/repository.ts`: feature-local data access and
  selectors for product slices listed in `features[].stateSlices`.
- `src/features/<feature>/seed.ts`: create-only seed stub for slices owned by
  that feature.
- `src/features/<feature>/controllers/<operationId>.ts`: thin generated route
  adapter.

The generator creates operation controllers and empty feature seed stubs for
owned slices. Create `service.ts` by hand when behavior needs orchestration.
Create `repository.ts` by hand for every completed feature that owns
non-infrastructure product state slices; `idCounters` alone does not need a
feature repository. Do not create a single `SharedRepository`,
`MockApiRepository`, or `src/shared/**repository**` module for product state.
Shared infrastructure helpers are fine, but product rules, selectors, and state
reads/writes belong in feature modules and feature repositories.

## Seeds

`features[].stateSlices` defines seed ownership. The generator creates
`src/features/<feature>/seed.ts` with empty defaults for owned slices; replace
product defaults according to `reference/seed-data.md`.

Generated `src/generated/mock-admin/state/seed.ts` is the seed composition root.
It creates the seed context, sets global state such as schema version and clock,
and aggregates feature seed functions:

```ts
const context = newSeedContext()

return {
  schemaVersion: 1,
  clock: {
    now: context.seedNow,
  },
  ...seedWorkspaces(context),
  ...seedNotes(context),
}
```

If a state slice is not listed in any `features[].stateSlices`, the generated
admin seed includes an empty fallback value. Prefer assigning every durable
state slice to exactly one feature in `profile.toml`. See
`reference/seed-data.md` for default seed population rules.

## Behavior Implementation

Feature services orchestrate behavior. Use feature repositories for domain
reads and writes. Use `MockStateRepository` directly only for cross-feature
transactions, mock clock helpers, ID counters, snapshot-level operations, or
other infrastructure behavior. Read-only composite services, such as search,
should consume other feature repositories instead of calling `getSlice` or
`setSlice` on product slices directly.

Repositories own collection mutation. Services should call named repository
methods such as `create`, `update`, `markDeleted`, `restore`, `remove`,
`addItem`, `listByParent`, or `descendantIds`. Do not put read-copy-overwrite
logic like `const rows = repo.all(); repo.setAll([...rows, row])` in services.
Prefer `find` or `require` over `byId`; avoid service-facing `setAll`,
`setItems`, and `replaceAll` feature APIs.

Keep route controllers thin. Do not put data-access logic in controllers or in
generated `src/generated/**` files. Controller input follows the generated
`openapi-ts` operation data shape: path parameters are under `input.path`, query
parameters are under `input.query`, and request bodies are under `input.body`.
Do not use `input.params`; that is Hono runtime terminology, not the generated
controller contract.
