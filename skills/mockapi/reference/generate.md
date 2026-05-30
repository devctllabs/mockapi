# mockapi generate

Generate creates a runnable TypeScript/Hono mock server from
`.mockapi/profile.toml`, then the agent completes operation behavior from
`.mockapi/behavior.md`.

Default `mockapi generate` means full runnable mock implementation. Do not stop
after scaffold/codegen unless the user explicitly asks for scaffold-only,
dry-run, boilerplate-only, or similar output.

## Workflow

### Preflight

1. Resolve the target root before checking sidecars:
   - If the user is already in the target repository root, use `.`.
   - If the user passes an OpenAPI path, prefer the nearest parent containing
     `.mockapi/profile.toml` whose `apis[].openapi` matches that path relative
     to the parent. Check `.mockapi` relative to that target root, not relative
     to the skill repository or current wrapper directory.
   - If no matching sidecar root exists, use the current repository root and let
     the profile workflow resolve the OpenAPI input.
2. Run the bundled sidecar preflight and classify it exactly once before any
   generation plan, OpenAPI search, repo-wide file scan, or sidecar edits:

```bash
<python> <skill-root>/scripts/preflight_generate.py --root .
```

   Read the JSON `classification` field:
   - `missing`: `.mockapi/profile.toml` is missing. Run the `mockapi profile`
     workflow first, then return to this workflow.
   - `repair`: `.mockapi/behavior.md` is missing or validation fails. Repair
     the existing sidecars before generation.
   - `valid`: validation passes and behavior anchors match the profile
     operation IDs. Reuse the existing `.mockapi/profile.toml` and
     `.mockapi/behavior.md`; do not plan to write, recreate, or profile them
     again.
   If independent inspection shows sidecars no longer match the OpenAPI
   operation IDs, treat that as `repair`: refresh the profile sidecars before
   generation.
   When the preflight is `valid`, explicitly say the existing sidecars are being
   reused. A `generate` plan for valid sidecars must start from validation and
   generation, not from "write profile" or "profile the OpenAPI".
   Use direct file tests such as `test -f .mockapi/profile.toml` only as a
   fallback diagnostic. If searching for sidecars manually, use
   `rg --files --hidden -g '.mockapi/**' -g '!**/node_modules/**'`. Do not use
   `rg --files -g '.mockapi/**'` without `--hidden`; `.mockapi` is a
   dot-directory and ripgrep will otherwise skip it.

### Scaffold and Codegen

3. Validate `.mockapi/profile.toml` and Markdown sidecars:

```bash
<python> <skill-root>/scripts/validate_profile.py
```

Resolve `<python>` to Python 3.11+ before running bundled scripts. If validation
fails, update sidecars or report blockers. Do not run `generate.py` on invalid
profile data.

4. Run the bundled Python generator with codegen enabled. Do not skip this step
   for a `generate` command after validation succeeds:

```bash
<python> <skill-root>/scripts/generate.py --root . --profile .mockapi/profile.toml --run-codegen
```

Generation uses `profile.project.target.packagePath` as the canonical output
root. Apply output-location requests by intent:

- Durable output intent: if the user requests a specific generated
  project/package/folder location without framing it as temporary, update
  `profile.project.target.packagePath`, then generate without `--out`.
- One-off output intent: if the user frames the location as temporary,
  experimental, dry-run-only, or provides CLI `--out`, run `generate.py` with
  `--out` and/or `--dry-run` and do not update `profile.toml`. `--dry-run`
  never installs dependencies or runs codegen.
- Ambiguous conflict: if the profile already has a non-default custom
  `packagePath` and the user requests a different location without clear
  durability, ask whether to update the canonical path or use a one-off
  override.

With `--run-codegen`, the generator detects the generated package manager,
installs dependencies when `node_modules` is missing, and runs the generated
package `codegen` script before the agent edits controller wiring or feature
implementation files. When pnpm is detected, the generator first creates a
create-only `pnpm-workspace.yaml` with `allowBuilds.esbuild: true` to avoid an
interactive `pnpm approve-builds` blocker. If generator JSON returns `ok:
false`, stop and report its `diagnostics`; fix package-manager, install, or
codegen blockers before editing LLM-owned controller or feature implementation
files.

The Python generator writes `openapi/admin.source.yaml` as the internal admin
contract input. It may contain external product schema refs. The generated
`codegen` script reads `openapi/admin.source.yaml`, writes a self-contained
`openapi/admin.yaml`, and only then runs `openapi-ts`. To refresh `admin.yaml`
from `.mockapi/profile.toml` and product OpenAPI changes, rerun
`mockapi generate --run-codegen`.

5. Inspect generation results. Existing scaffold and feature files are skipped,
   not overwritten. New endpoint starters are added under
   `src/features/<feature>/controllers/<operationId>.ts` when those files are
   missing. Empty `src/features/<feature>/seed.ts` stubs are generated for
   features that own state slices. Feature services and repositories are not
   generated.
6. Read the generator JSON `packageManager` and `codegen` fields. They include
   the detected package manager and the manual `codegen.codegenCommand`.
   Use that command later only when generated package OpenAPI inputs are already
   current. Rerun `mockapi generate --run-codegen` when `.mockapi/profile.toml`
   or product schema refs that feed admin state change. Do not hand-roll package
   manager checks or use interactive shells such as `zsh -ic`; nvm-managed tools
   may only be available after detector-provided PATH recovery. To recompute the
   commands manually, run:

```bash
<python> <skill-root>/scripts/detect_package_manager.py --root . --profile .mockapi/profile.toml
```

The standalone detector remains the manual regeneration/diagnostic path. It
respects explicit `packageManager` fields. Without an explicit field, it
prefers pnpm when available or when `pnpm-lock.yaml` is present, then detects
Yarn, Bun, or npm from lockfiles, and finally falls back to npm. It also checks
nvm-managed Node installations and corepack for pnpm/Yarn.

### Behavior Implementation

7. After codegen succeeds, read `reference/mock-server-structure.md`,
   `reference/mock-server-examples.md`, `reference/seed-data.md`,
   `reference/testing.md`, `reference/mock-server-quality.md`,
   `.mockapi/behavior.md`, generated `src/generated/**`,
   `src/controllers.ts`, and `src/features/**`. Create
   feature-local `service.ts` when behavior needs orchestration. Create
   feature-local `repository.ts` for every completed feature that owns
   non-infrastructure state slices; `idCounters` alone does not need a
   repository. Replace generated product seed stub defaults unless
   `.mockapi/profile.toml` sets `state.seed = false`. Extend
   `MockApiDependencies` in `src/controllers.ts`, instantiate
   repositories/services from the shared `MockStateRepository`, and pass
   dependencies into operation controllers through `deps`. Keep feature seed
   data in `src/features/<feature>/seed.ts`; generated
   `src/generated/mock-admin/state/seed.ts` will aggregate feature seed
   functions.
   Operation controller inputs use the generated `openapi-ts` data shape:
   OpenAPI path parameters live under `input.path`, not `input.params`. For
   example, use `input.path.workspaceId` or destructure `({ path, query })`;
   do not copy Hono terminology such as `params` into feature controllers.
   Follow the repository/service naming vocabulary in
   `reference/mock-server-examples.md`: prefer `find`/`require`, named
   mutations such as `create`/`update`/`markDeleted`/`restore`, and avoid
   service-facing `setAll`, `setItems`, or `replaceAll` APIs.
   Do not create a single shared product repository. Services may use
   `MockStateRepository` directly for transactions, mock clock helpers,
   `idCounters`, and cross-repository coordination only; product state reads and
   writes go through feature repositories. Read-only composite features should
   consume other feature repositories instead of raw state slices. Keep operation
   controllers thin; do not put data-access logic there. Replace controller
   TODOs from the matching behavior anchors. Use counter IDs with `idCounters`
   and `newIdAllocator` by default for create operations; slug-style IDs require
   explicit behavior opt-in. Allocate IDs once per transaction and pass the
   allocator into helpers that need additional IDs. Do not infer behavior from
   operation shape when the anchor has open questions.
   Add adjacent Vitest unit tests for completed LLM-owned feature behavior:
   `service.test.ts` next to `service.ts`, `repository.test.ts` next to
   `repository.ts`, and `<helper>.test.ts` next to feature-local domain helpers.
   Keep generated operation controller adapter tests out of scope unless an
   adapter contains non-trivial normalization. Keep HTTP workflow smoke tests in
   `src/app.test.ts`.

### Final Verification

8. After LLM-owned implementation edits, run the returned
   `packageManager.commands.check` from the generator JSON in `packageRoot`.
   Then run the generated package `test` script, if present. Generated mock
   server templates include Vitest by default; put HTTP smoke tests in
   `src/app.test.ts`, config/env tests in `src/config.test.ts`, and unit tests
   for feature behavior beside the source files they cover.
   Then run the final quality checker:

```bash
<python> <skill-root>/scripts/check_generated_quality.py --package-root <packageRoot> --profile .mockapi/profile.toml
```

   Do not run `check_generated_quality.py` before replacing generated TODO
   adapters, filling required product seed data, wiring dependencies, and adding
   smoke tests. A fresh scaffold is expected to fail this checker; early failure
   is not a reason to stop at scaffold handoff.
   Fix quality errors before handoff. Fix obvious warnings or report them as
   residual risks. Do not start the long-running `dev` script unless the user
   asks. Do not run dependency installation inside the skill folder. Do not
   modify generated `src/generated/**` files by hand.

If repairing an existing generated package that still uses
`params: context.req.param()` in `src/lib/honoMockRuntime.ts`, change that
runtime input key to `path` and update every feature controller that reads
`input.params.<name>` to read `input.path.<name>`. Runtime-only repair is
incomplete.

## Generation Policy

- OpenAPI runtime/config files and `src/generated/mock-admin/state/**` may be
  overwritten.
- Template scaffolds such as `src/app.ts`, `src/server.ts`,
  `src/controllers.ts`, and `src/lib/**` are create-only.
- `src/controllers.ts` is the LLM-owned composition root for DI and route
  controller wiring. If the profile API set changes after initial generation,
  update `src/app.ts` registrations manually as part of the same LLM-owned
  wiring pass.
- `src/features/**` is reviewable behavior. Generation creates missing
  operation controller TODO adapters and create-only seed stubs for owned state
  slices. Feature services and repositories are LLM-owned and created only when
  behavior needs them. Complete product seed data according to
  `reference/seed-data.md`.
- Every operation controller is generated as a typed TODO adapter for LLM
  completion.
