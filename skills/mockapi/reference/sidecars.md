# mockapi Sidecars

The profile sidecars are the durable contract between behavior analysis and
generation.

## `.mockapi/profile.toml`

Minimum root fields:

- `schemaVersion: 1`
- `generator.name`, `generator.version`
- `project.root`, `project.target.packagePath`, `packageName`, `serverName`
- `apis[]` with `name`, `openapi`, optional `basePath`, `contractOutput`,
  `runtimeOutput`
- `features[]` with `name`, optional `stateSlices`, `operations`
- `state.schemaVersion: 1`, `state.slices[]`
- optional `state.seed` boolean
- `operations[]` with `operationId`, `api`, `feature`, `method`, `path`

`apis[].openapi` may be repository-relative, absolute, or HTTP(S). Preserve URLs
as URLs during generation.

`project.target.packagePath` is the required canonical output root for the
generated mock-server package, relative to `project.root`.

Use TOML arrays of tables for repeated records: `[[apis]]`, `[[features]]`,
`[[state.slices]]`, and `[[operations]]`.

Authoritative `[[state.slices]]` fields:

- `name` required string: stable state key used in mock state and feature
  ownership. Must be TypeScript identifier-safe
  (`^[A-Za-z_$][A-Za-z0-9_$]*$`); prefer camelCase names such as
  `activeWorkspace`.
- `recordType` required string: persisted record shape, usually an OpenAPI
  schema name or a TS-only generic record type.
- `array` required boolean: `true` for collection slices, `false` for singleton
  slices.
- `idField` optional string: identifier field for array records.
- `softDeleteField` optional string: field used by generated helpers and LLM
  behavior for soft-deleted records.
- `schemaRef` optional string: explicit schema source for typed admin state;
  use it when multiple APIs are configured or when the schema is in another
  local OpenAPI file.

`state.seed` controls initial product seed data. Missing `state.seed` defaults
to `true`. Set `seed = false` only when the user explicitly requests an empty
initial product state:

```toml
[state]
schemaVersion = 1
seed = false
```

`seed = false` does not disable generated `seedState()`, schema version, mock
clock, or infrastructure state. See `reference/seed-data.md`.

For generated IDs, include an `idCounters` singleton slice and use
`newIdAllocator` from `src/lib/ids.ts` in feature services:

```toml
[[state.slices]]
name = "idCounters"
recordType = "Record<string, number>"
array = false
```

`features[].stateSlices` is seed ownership. Each state slice may be listed by
at most one feature. Feature code can still read other slices through
repositories/services; do not list read-only dependencies in `stateSlices`.

`state.slices[].recordType` names the persisted record shape. For a single API,
the generator treats `recordType = "Workspace"` as
`<only-api>#/components/schemas/Workspace` when rendering the typed admin
state contract. With multiple APIs, set
`schemaRef = "<api-name>#/components/schemas/<SchemaName>"` for each typed
slice. TS-only generic slices such as `Record<string, number>` do not need
`schemaRef`.

Typed state slices must reference local OpenAPI files. HTTP OpenAPI URLs are
allowed for route generation, but admin state schema copying does not inline
remote schema refs.

If a state schema is not exported from the API root file, use a file-qualified
schema ref. The path is relative to the directory containing `apis[].openapi`:

```toml
[[state.slices]]
name = "trashItems"
recordType = "TrashItem"
schemaRef = "product-api:./domains/trash.yaml#/components/schemas/TrashItem"
array = true
idField = "id"
```

Minimal example:

```toml
schemaVersion = 1

[generator]
name = "mockapi"
version = "0.1.0"

[project]
root = "."

[project.target]
packagePath = "mock-server"
packageName = "@local/mock-server"
serverName = "Mock API"

[[apis]]
name = "product-api"
openapi = "openapi.yaml"
basePath = "/api"

[[features]]
name = "workspaces"
stateSlices = ["workspaces"]
operations = ["listWorkspaces"]

[state]
schemaVersion = 1

[[state.slices]]
name = "workspaces"
recordType = "Workspace"
array = true
idField = "id"

[[operations]]
operationId = "listWorkspaces"
api = "product-api"
feature = "workspaces"
method = "GET"
path = "/workspaces"
```

## Behavior Anchors

Every operation maps to `## operation:<operationId>` in `.mockapi/behavior.md`.
The profile is a structural index; do not encode behavior categories in
`profile.toml`. Generated services are typed TODOs that the LLM completes from
`.mockapi/behavior.md`.

## `.mockapi/behavior.md`

Use stable anchors:

```md
## operation:startReviewSession

Status: open-questions

Open questions:
- What state is created or updated when the session starts?
- Should starting an already active session return the existing session or fail?
```

Matching the profile example:

```md
## operation:listWorkspaces

Status: inferred

Return workspaces from in-memory state. Use response shape and status codes from
OpenAPI.
```

Confirmed user behavior example:

```md
## operation:createWorkspace

Status: confirmed

Create a workspace in memory with a generated id and the current mock clock
timestamp. Names must be unique among non-deleted workspaces.
```

After `Status`, write freeform operation behavior for the LLM generator. Do not
require fixed subsections such as `State`, `Response`, `Errors`, or
`Acceptance`. Include only behavior that is not already safe to derive from the
OpenAPI contract and repository context.

Supported statuses:

- `Status: inferred`: trivial behavior inferred by the LLM from OpenAPI and
  repository context.
- `Status: confirmed`: non-trivial behavior explicitly confirmed by the user.
- `Status: open-questions`: non-trivial behavior still waiting on user answers.

Keep open questions visible under the operation anchor. Open questions mean
concrete operation behavior was asked and remains unresolved; they are not a
substitute for asking the behavior interview.

The validator checks anchors structurally: every `profile.toml` operation must
have a matching `## operation:<operationId>` section, extra anchors are
warnings, and duplicate or invalid anchors are errors.
