<h1 align="center">
  <a href="https://github.com/devctllabs/mockapi#readme">
    <img alt="mockapi" width="400" src="assets/logo.png">
  </a>
</h1>

<p align="center">
  Generate stateful TypeScript mock API servers from OpenAPI contracts
</p>

<p align="center">
  <img alt="version 0.1.0" src="https://img.shields.io/badge/version-0.1.0-2f6f5e?style=flat-square">
  <img alt="license Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-4a5568?style=flat-square">
  <img alt="node &gt;=20" src="https://img.shields.io/badge/node-%3E%3D20-339933?style=flat-square&amp;logo=node.js&amp;logoColor=white">
  <img alt="python &gt;=3.11" src="https://img.shields.io/badge/python-%3E%3D3.11-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white">
</p>

`mockapi` is an AI agent skill for teams that want realistic local APIs without
hand-writing mock servers. Give your coding agent an OpenAPI 3.0/3.1
contract, let it profile the API behavior, then generate a runnable Hono server
with typed routes, durable mock state, admin endpoints, seed data, tests, and
quality checks.

## Install

Install with the `skills` CLI:

```bash
npx skills add devctllabs/mockapi
```

## Quick Start

From a repository that contains an OpenAPI contract:

### 1. Profile the API

Ask your coding agent to analyze the contract:

```text
/mockapi profile api/openapi.yaml
```

Recommendation: run this step in Plan Mode. For non-trivial operations, the agent
can interview you about ambiguous behavior before writing `.mockapi/profile.toml`
and `.mockapi/behavior.md`.

This creates durable sidecars that describe the API structure and behavior:

```text
.mockapi/
  profile.toml    # operation index, state slices, output package settings
  behavior.md     # behavior anchors for each OpenAPI operation
```

### 2. Generate the mock server

Ask your coding agent to generate the package:

```text
/mockapi generate
```

This creates a runnable TypeScript/Hono mock server:

```text
mock-server/
  openapi/
    admin.yaml
  src/
    app.ts
    server.ts
    controllers.ts
    features/
      <feature>/
        controllers/
        repository.ts
        service.ts
        seed.ts
    generated/
      <product-api>/
      mock-admin/
```

### 3. Start the server

Run the generated package:

```bash
cd mock-server
pnpm dev
```

The server starts locally with product routes and `/__mock/*` admin endpoints.

## What You Get

- **OpenAPI-first generation**: product routes and request/response types come
  directly from your OpenAPI 3.0/3.1 contract.
- **Stateful behavior**: generated servers use in-memory state with optional
  JSON snapshot persistence.
- **Typed Hono server**: each package is a TypeScript/Hono server with generated
  contract types and runtime adapters.
- **Admin API included**: every server exposes `/__mock/*` endpoints for health,
  reset, state inspection, snapshots, and mock clock control.
- **Agent-readable behavior**: `.mockapi/behavior.md` stores operation-specific
  behavior so implementation decisions survive regeneration.
- **Reviewable feature code**: generated infrastructure is separated from
  feature modules that your agent can complete, test, and review.
- **Quality gates**: validators and final checks catch invalid sidecars,
  unfinished TODO adapters, empty seed data, and common architecture drift.

## What's Included

### The Skill: `mockapi`

| Workflow | What it does |
|----------|--------------|
| `/mockapi profile <openapi>` | Analyzes the OpenAPI contract, interviews for ambiguous behavior, and writes `.mockapi/profile.toml` plus `.mockapi/behavior.md`. |
| `/mockapi generate` | Generates the TypeScript/Hono mock-server package from the sidecars. |
| `/mockapi <freeform request>` | Routes freeform requests to the right workflow. |

### Reference Docs

| Reference | Covers |
|-----------|--------|
| [profile](skills/mockapi/reference/profile.md) | Behavior interview, OpenAPI profiling, sidecar creation |
| [generate](skills/mockapi/reference/generate.md) | Scaffold generation, codegen, implementation workflow |
| [sidecars](skills/mockapi/reference/sidecars.md) | `.mockapi/profile.toml` and `.mockapi/behavior.md` format |
| [generated-server](skills/mockapi/reference/generated-server.md) | Generated Hono package architecture |
| [mock-server-examples](skills/mockapi/reference/mock-server-examples.md) | Repository, service, and controller patterns |
| [mock-server-quality](skills/mockapi/reference/mock-server-quality.md) | Final quality gate expectations |
| [seed-data](skills/mockapi/reference/seed-data.md) | Initial mock state policy |

## How It Works

1. **Profile the contract**

   The agent reads the OpenAPI contract and nearby project context, then writes
   `.mockapi/profile.toml` and `.mockapi/behavior.md`.

2. **Confirm behavior**

   Trivial operations can be inferred. For non-trivial workflows, the agent asks
   targeted questions about state changes, responses, errors, generated IDs,
   seed data, auth simulation, and edge cases.

3. **Generate the server**

   The generator creates the TypeScript/Hono package, admin OpenAPI contract,
   runtime adapters, feature controller starters, and seed hooks.

4. **Complete feature behavior**

   Your agent fills feature repositories, services, seed data, and HTTP smoke
   tests from the behavior sidecar.

5. **Run checks**

   The generated package typechecks and tests with normal package-manager
   commands, then `mockapi` runs its final quality gate.

## Generated Server Features

Generated packages include:

- `GET /__mock/health`
- `POST /__mock/reset`
- `GET /__mock/state`
- `PUT /__mock/state`
- `GET /__mock/snapshot`
- `POST /__mock/snapshot`
- `PUT /__mock/clock`

By default, runtime state is persisted to:

```text
mock-server/.mockapi-runtime/db.json
```

Set `MOCK_API_STATE_FILE` to write snapshots somewhere else. Relative paths are
resolved from the generated package root.

## Advanced Scripts

Most users should use `/mockapi ...`; these scripts are useful for validation,
CI, and debugging.

| Script | Use it for | Example |
|--------|------------|---------|
| `preflight_generate.py` | Classify sidecars as `missing`, `repair`, or `valid` before generation. | `python skills/mockapi/scripts/preflight_generate.py --root .` |
| `validate_profile.py` | Validate `.mockapi/profile.toml` and `.mockapi/behavior.md`. | `python skills/mockapi/scripts/validate_profile.py --root .` |
| `generate.py` | Generate the mock-server package and run generated package codegen. | `python skills/mockapi/scripts/generate.py --root . --profile .mockapi/profile.toml --run-codegen` |
| `detect_package_manager.py` | Inspect the generated package manager and returned commands. | `python skills/mockapi/scripts/detect_package_manager.py --root . --profile .mockapi/profile.toml` |
| `check_generated_quality.py` | Run the final quality gate after feature behavior, seed data, and tests are implemented. | `python skills/mockapi/scripts/check_generated_quality.py --package-root mock-server --profile .mockapi/profile.toml` |

Do not run the final quality gate on a fresh scaffold; generated operation
controllers start as TODO adapters.

## Requirements

- Python 3.11+
- Node.js 20+
- An OpenAPI 3.0 or 3.1 YAML/JSON contract
- One of npm, pnpm, Yarn, or Bun for the generated package

The generator detects the package manager for the generated server and uses the
matching install, codegen, check, and test commands.

## Why `mockapi`

Most mock APIs are either too static for real product flows or too custom to
regenerate safely. `mockapi` keeps the contract, behavior notes, generated
infrastructure, and reviewable feature code in separate layers:

- OpenAPI stays the source of truth for route shape.
- `.mockapi/profile.toml` stays the source of truth for generation.
- `.mockapi/behavior.md` stays the source of truth for operation behavior.
- `src/generated/**` can be overwritten.
- `src/features/**` stays reviewable product mock behavior.

That split gives agents enough structure to generate consistently while keeping
the behavior code understandable for humans.

## License

Apache-2.0
