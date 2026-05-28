---
name: mockapi
description: Create stateful TypeScript/Hono mock API servers from OpenAPI 3.0/3.1 contracts. Use for building OpenAPI-based mock APIs, creating or repairing .mockapi sidecars, validating mock profiles, generating admin state endpoints, or freeform requests such as "mockapi build a mock server for api/openapi.yaml".
---

# mockapi

Use this skill to create stateful mock API servers from OpenAPI contracts. The
agent owns behavior analysis and sidecar authoring; bundled scripts only perform
structural validation and deterministic typed scaffolding. Generated operation
services are TODOs; the agent completes wiring and behavior from
`.mockapi/behavior.md` anchors.

## Command Router

Route invocations:

1. No argument: show a short menu with `profile`, `generate`, and freeform
   examples. Ask what the user wants to do.
2. First word `profile`: read `reference/profile.md` and follow that workflow.
   Everything after `profile` is the target or context.
3. First word `generate`: before any OpenAPI search or repo-wide file scan,
   read `reference/generate.md` and run the generate sidecar preflight from
   that workflow. Everything after `generate` is the target or context. After
   the profile and sidecars are present and validation succeeds, always run
   `<python> <skill-root>/scripts/generate.py`; do not satisfy a `generate`
   command by only describing, planning, or hand-writing the scaffold.
4. Any other first word: treat the entire argument as a general mockapi request.
   Do not reject unknown first words merely because they are not commands.

General mockapi request routing:

- Mock-server creation requests such as "make", "build", "create", "generate",
  "scaffold", or "use this OpenAPI" route to `reference/generate.md`.
  `generate` auto-runs the profile workflow when sidecars are missing.
- Profile, analyze, describe, or sidecar-only requests route to
  `reference/profile.md`.
- Validate, check, repair, or diagnose sidecar requests run
  `scripts/validate_profile.py`, read `reference/sidecars.md`, and repair
  or report blockers as needed. The validator checks `profile.toml` and
  `behavior.md` unless `--profile-only` is used.
- Questions about existing generated mock-server code read
  `reference/generated-server.md`, `reference/mock-server-structure.md`, and
  `reference/mock-server-examples.md`, then inspect the relevant files. When
  finishing or reviewing LLM-owned generated server code, also read
  `reference/mock-server-quality.md`.

If the freeform intent remains ambiguous after inspecting the repository, ask
one concise clarification before mutating files. Do not invent extra commands or
run unbundled scripts.

## Runtime Rules

- Requires Python 3.11+ for bundled scripts. Resolve `<python>` to an
  executable whose version is 3.11+ before running script examples. If no
  suitable interpreter exists, stop and report the requirement to the user.
  Bundled CLI scripts also verify the active interpreter and fail with a clear
  error when it is too old.
- Resolve `<skill-root>` to the directory containing this `SKILL.md`. Run shell
  command examples by replacing `<skill-root>` with that absolute or
  repository-relative skill directory.
- Run only committed bundled Python scripts from `scripts/*.py` during normal
  skill usage.
- Treat `reference/*.md` and the target repository context as the primary
  contract for agent decisions. Do not read script source as a source of
  profiling requirements during normal profile work.
- Use `reference/sidecars.md` as the authoritative sidecar schema, including
  valid `profile.toml` fields. If a needed sidecar shape is missing from the
  references, stop and report the exact documentation gap instead of inferring
  it from `scripts/mockapi_runtime/*.py`.
- Inspect bundled Python source only to diagnose a validator or generator defect
  after running the committed scripts. Do not use script source to discover
  valid sidecar fields, defaults, or profile behavior policy.
- Do not run dependency installation inside the skill folder.
- For generated package dependency/script steps, use
  `scripts/detect_package_manager.py`; do not hand-roll `command -v` package
  manager checks or rely on interactive shell startup files.
- In `generate` workflows, run generated package codegen before implementing or
  editing LLM-owned controller wiring or feature modules.
- Do not edit OpenAPI contracts unless the user explicitly requests contract
  changes.
- Treat `.mockapi/profile.toml` and `.mockapi/behavior.md` as the durable
  source of truth for generation.
- For any `generate` workflow, run `scripts/generate.py --run-codegen` after
  successful validation. If validation fails, repair sidecars or report blockers
  instead of running the generator on invalid data.
- Treat `profile.toml` as the structural operation index. Implement operation
  behavior from the matching `behavior.md` anchor, not from operation shape.
- Use `reference/sidecars.md` for sidecar shape and validation expectations.
- Use `reference/generated-server.md`, `reference/mock-server-structure.md`,
  `reference/mock-server-examples.md`, `reference/seed-data.md`, and
  `reference/mock-server-quality.md` when inspecting or finishing generated
  server code.

## Bundled Scripts

Validate sidecars:

```bash
<python> <skill-root>/scripts/validate_profile.py
```

Preflight sidecars for generate:

```bash
<python> <skill-root>/scripts/preflight_generate.py --root .
```

Profile-only validation:

```bash
<python> <skill-root>/scripts/validate_profile.py --profile-only
```

Generate server scaffold and run codegen:

```bash
<python> <skill-root>/scripts/generate.py --root . --profile .mockapi/profile.toml --run-codegen
```

Detect generated package manager for manual regeneration:

```bash
<python> <skill-root>/scripts/detect_package_manager.py --root . --profile .mockapi/profile.toml
```

Final quality gate after implementation only:

```bash
<python> <skill-root>/scripts/check_generated_quality.py --package-root <packageRoot> --profile .mockapi/profile.toml
```
