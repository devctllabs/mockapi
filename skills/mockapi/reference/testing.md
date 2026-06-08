# Mock Server Testing

Generated packages use Vitest. Add tests during the LLM-owned behavior
implementation phase, after `generate.py --run-codegen` and after generated
runtime types exist.

## Feature Unit Tests

Write unit tests beside the feature source file they cover:

- `src/features/<feature>/service.test.ts` for `service.ts`
- `src/features/<feature>/repository.test.ts` for `repository.ts`
- `src/features/<feature>/<helper>.test.ts` for feature-local domain helpers
- `src/lib/stateStore.test.ts` when changing the generated `@msw/data` store or
  persistence adapters

Unit-test completed LLM-owned behavior, not deterministic generated scaffold.
Do not add tests for generated TODO adapters or thin operation controllers by
default. Add an adjacent controller test only when the controller performs
non-trivial request normalization or branching that is not covered by the
service or app smoke tests.

Prefer narrow tests over broad snapshots. Exercise repository selectors and
mutations, service orchestration, ID allocation behavior, soft-delete flows,
validation branches, and feature-local helper rules that came from
`.mockapi/behavior.md`.

## HTTP Smoke Tests

Keep HTTP workflow smoke tests in `src/app.test.ts` by default. Cover:

- custom `basePath` mounting
- one representative workflow for each non-trivial feature
- create operations that return generated counter IDs
- admin state reset or inspection when admin endpoints are generated

Use `src/config.test.ts` only for config/env resolution tests. Split a workflow
out of `src/app.test.ts` only when the app-level file becomes hard to maintain;
even then, keep source-adjacent unit tests for feature internals.

## Verification

Run the generated package check command first, then the generated package
`test` script, then `check_generated_quality.py`. Fix quality errors before
handoff. Fix obvious test warnings, or report them as residual risk.
