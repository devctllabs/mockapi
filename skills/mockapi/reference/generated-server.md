# Generated Server

Generated packages are TypeScript/Hono mock servers with:

- product OpenAPI routes from `.mockapi/profile.toml`
- `/__mock/*` admin endpoints
- in-memory state with optional JSON snapshot persistence
- generated contract/runtime code under `src/generated/**`
- LLM-owned controller wiring and feature behavior

For the canonical project layout, ownership rules, and examples, read
`reference/mock-server-structure.md` and `reference/mock-server-examples.md`.

## Generated Zones

Overwrite-safe:

- `src/generated/**`
- `openapi-ts.config.ts`
- `openapi/admin.source.yaml`
- `openapi/admin.yaml`
- `scripts/codegen-mock-runtime.ts`
- `scripts/codegen-admin-openapi.ts`
- `scripts/lib/mockRuntimeCodegen.ts`
- `src/generated/mock-admin/state/**`

Create-only scaffold:

- `src/app.ts`
- `src/server.ts`
- `src/controllers.ts`
- `src/lib/**`

Reviewable behavior:

- `src/features/**`

Scaffold and feature files are create-only. Generation may add missing files for
new operations, but it must not rewrite existing scaffold or feature files. New
endpoint starters are written to:

- `src/features/<feature>/controllers/<operationId>.ts`
- `src/features/<feature>/seed.ts` for features that own state slices

The controller file is a thin typed TODO adapter. Root `src/controllers.ts` is
LLM-owned and must be updated when dependencies or operation wiring change after
initial generation.

`src/generated/mock-admin/state/**` is generated admin infrastructure. Do not
edit it by hand; put seed data in feature seed files and behavior in feature
modules.

## Feature Modules

Create feature services only when behavior needs orchestration, except generated
seed stubs for owned slices. Once behavior is completed, every feature that owns
non-infrastructure product state slices must have a feature repository:

- `src/features/<feature>/controllers/<operationId>.ts`: thin generated adapter.
- `src/features/<feature>/service.ts`: feature behavior from
  `.mockapi/behavior.md`, usually shared by multiple operations.
- `src/features/<feature>/repository.ts`: required feature-local data access and
  selectors for owned product state slices.
- `src/features/<feature>/seed.ts`: create-only seed stub for
  `features[].stateSlices`; replace empty product defaults according to
  `reference/seed-data.md`.
- `src/controllers.ts`: composition root that creates repositories and passes
  them through `MockApiDependencies`.

Keep product/domain helpers near their owning feature, for example
`src/features/notes/noteDetails.ts` or
`src/features/location-path/resolver.ts`. Use `src/lib/**` only for
product-agnostic infrastructure helpers such as clone, errors, request context,
IDs, soft delete, and sorting. Do not add product-domain modules such as
`src/lib/notes.ts`, `src/lib/deckStats.ts`, or `src/lib/tree.ts`.

`MockStateRepository` is the low-level in-memory state store. Feature
repositories sit above it as domain slice facades. They use `getSlice` and
`setSlice` to expose methods such as `all`, `visible`, `find`, `require`,
`create`, `update`, `markDeleted`, `restore`, `remove`, and feature-specific
selectors. Use `find` or `require` instead of `byId`; avoid service-facing
`setAll`, `setItems`, or `replaceAll` feature APIs. Keep canonical state as
arrays or singleton slices by default, not maps.

Feature services own orchestration. They must use feature repositories for
domain resource reads and writes, but may use `MockStateRepository` directly for
transaction boundaries, mock clock helpers, ID counters, and cross-repository
coordination. Read-only composite services should consume other feature
repositories instead of raw state slices. Services should call named repository
methods; do not implement `const rows = repo.all(); repo.setAll([...rows, row])`
or similar read-copy-overwrite mutation in services. Keep operation controllers
as adapters from generated runtime input shape to service method calls.

For concrete repository/service naming, composition root, soft delete, trash,
counter, and read-only composite examples, use `reference/mock-server-examples.md`.

Example:

```ts
import type { MockStateRepository } from '../../generated/mock-admin/state/repository.ts'
import type { WorkspaceRecord } from '../../generated/mock-admin/contract/index.ts'
import { visible } from '../../lib/softDelete.ts'

export class WorkspacesRepository {
  constructor(private readonly stateStore: MockStateRepository) {}

  all() {
    return this.stateStore.getSlice('workspaces')
  }

  visible() {
    return visible(this.all())
  }

  find(workspaceId: string) {
    return this.all().find((workspace) => workspace.id === workspaceId)
  }

  create(workspace: WorkspaceRecord) {
    this.stateStore.setSlice('workspaces', [workspace, ...this.all()])
  }
}
```

Wire repositories in `src/controllers.ts`:

```ts
export type MockApiDependencies = {
  stateRepository: MockStateRepository
  workspacesRepository: WorkspacesRepository
}

const stateRepository = new MockStateRepository(options)
const workspacesRepository = new WorkspacesRepository(stateRepository)
const deps: MockApiDependencies = {
  stateRepository,
  workspacesRepository,
}
```

Use feature services from operation controllers:

```ts
export const newListWorkspacesController = (
  deps: MockApiDependencies,
): Pick<ProductMockControllers, 'listWorkspaces'> => ({
  listWorkspaces: async () => deps.workspaceService.list(),
})
```

For OpenAPI path parameters, use the generated operation data shape
`input.path`, not Hono-style `input.params`:

```ts
export const newListWorkspaceDecksController = (
  deps: MockApiDependencies,
): Pick<ProductMockControllers, 'listWorkspaceDecks'> => ({
  listWorkspaceDecks: async ({ path, query }) =>
    deps.decksService.listWorkspaceDecks(path.workspaceId, query),
})
```

## Feature Seeds

Keep seed data near the owning feature. Generated feature seed stubs return only
their owned state slices and may start empty:

```ts
import type { SeedContext } from '../../generated/mock-admin/state/seed.ts'
import type { MockState } from '../../generated/mock-admin/contract/index.ts'

export const seedWorkspaces = (_context: SeedContext): Pick<MockState, 'workspaces'> => ({
  workspaces: [],
})
```

Generated `src/generated/mock-admin/state/seed.ts` creates the `SeedContext`,
sets global state such as schema version and mock clock, and spreads feature
seed functions. Do not move seed data back into the admin seed module. Use
`reference/seed-data.md` for the required initial dataset policy.

## State Types

Use `src/generated/mock-admin/contract/index.ts` as the canonical admin state
contract. It exports `MockState`, `MockClock`, and admin record shapes. Feature
code should import record shapes from generated product/admin contracts or
define feature-local aliases when a generated shape is not enough.

## Admin API

Every generated server includes:

- `GET /__mock/health`
- `POST /__mock/reset`
- `GET /__mock/state`
- `PUT /__mock/state`
- `GET /__mock/snapshot`
- `POST /__mock/snapshot`
- `PUT /__mock/clock`

The server binds to `127.0.0.1` by default. Binding to `0.0.0.0` must be an
explicit environment choice.

Runtime state persists to `.mockapi-runtime/db.json` inside the generated
package by default. Startup logs include the absolute path as
`State snapshot: /full-path/to/mock-server/.mockapi-runtime/db.json`.
Set `MOCK_API_STATE_FILE` to use a different snapshot file; relative override
paths resolve from the generated package root.

`openapi/admin.source.yaml` is generated from `.mockapi/profile.toml` and may
contain external product schema refs. `scripts/codegen-admin-openapi.ts` runs
before `openapi-ts`, copies the transitive state schema graph into
`openapi/admin.yaml`, and rewrites refs to local `#/components/schemas/*` refs.
Treat `openapi/admin.yaml` as the final self-contained mock-admin contract after
`mockapi generate --run-codegen`; `admin.source.yaml` is only a generated
codegen input.
