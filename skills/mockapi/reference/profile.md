# mockapi profile

Profile turns an OpenAPI contract plus developer answers into durable sidecars:

```text
.mockapi/profile.toml
.mockapi/behavior.md
```

## Workflow

1. Resolve the OpenAPI 3.0/3.1 YAML/JSON input path or URL:
   - If the user provided a path or URL, use it.
   - Otherwise inspect existing `.mockapi/profile.toml` for `apis[].openapi`.
   - Otherwise search likely files such as `openapi.*`, `swagger.*`,
     `api/**`, `apis/**`, `docs/**`, and `spec/**`.
   - If exactly one credible candidate is found, use it and state the choice.
   - If multiple or no credible candidates are found, ask the user for the
     OpenAPI path or URL before profiling.
2. Read the contract and nearby repository context that clarifies behavior:
   clients, tests, route handlers, domain models, fixtures, and docs.
3. Profile every operation as structural route metadata. The generator creates
   typed TODO services; the LLM implements all behavior from the matching
   `operation:<operationId>` section in `.mockapi/behavior.md`.
4. If an operation is non-trivial, stop the normal profile workflow and ask a
   grouped behavior interview immediately. This is a required gate before any
   final profile plan, completion summary, sidecar write, or validator run.
   Repository context can guide the questions, but it does not make non-trivial
   behavior `confirmed`; only the developer can confirm it. Group related
   operations by feature and ask targeted questions for behavior that cannot be
   safely inferred as a trivial mock from the contract and repository context:
   custom workflows, state transitions, cross-resource writes, conflicts,
   validation rules, generated ID policy, seed data, mock clock behavior,
   auth/security simulation, and acceptance scenarios.
   If the developer chooses a conservative profile, record unknown behavior as
   open questions instead of inventing application workflows or searching
   generator internals for a business decision; it does not skip the behavior
   interview.
5. Write `.mockapi/profile.toml` as structured machine-readable data. For every
   operation, write `.mockapi/behavior.md` with a stable
   `## operation:<operationId>` section.
6. Run the bundled validator when sidecars exist:

```bash
<python> <skill-root>/scripts/validate_profile.py
```

Resolve `<python>` to Python 3.11+ before running bundled scripts. The
validator checks `profile.toml`, required `behavior.md` operation anchors for
every operation. If validation fails, update sidecars or report blockers. Do
not silently invent uncertain business behavior. The default paths are
`.mockapi/profile.toml` and `.mockapi/behavior.md`; use `--root` or explicit
path flags only for non-default layouts.

## Target Package Defaults

Set `project.target.packagePath` during profiling. This is the canonical output
root for the generated mock server, relative to `project.root`.

Use `mock-server` by default. Do not ask the developer for an output path in the
normal single-repository case. Ask during profiling only when repository context
shows multiple credible package locations, such as `apps/`, `packages/`, an
existing `mock-server`, or an explicit output-location hint. Record the chosen
path in `profile.toml`.

## Behavior Interview

For each operation, `.mockapi/behavior.md` must contain one of:

- inferred behavior for trivial operations
- confirmed behavior from developer answers
- explicit open questions gathered during the behavior interview

The interview response must contain the actual questions. Do not merely say
that the interview will start. Do not write sidecars, run validation, present a
final profile plan, or summarize profiling as complete until the developer
answers, declines, or explicitly says the behavior is unknown.

If the developer cannot answer or declines, record the unknown under the
operation anchor. If many operations share the same workflow, ask once for the
workflow and map the answer back to each operation anchor.

## Operation Behavior Policy

Do not ask the developer to choose implementation categories. The profile is
not a behavior classifier. It is a structural index that points each operation
at a behavior anchor. Inferred behavior, user-confirmed behavior, and open
questions live under that anchor in `.mockapi/behavior.md`.

Behavior interview questions must be operation-focused. Ask what the operation
does to state, response bodies, errors, and edge cases. Ask these questions for
every non-trivial operation. Do not ask meta-choice questions such as:

- how unconfirmed operations should be profiled
- which implementation category a workflow group should use
- whether tree mutations should use an inferred relationship model

For tree, review, search, trash, reset, bootstrap, settings, or similar
workflows, ask concrete behavior questions for the relevant operation anchors.
Open questions mean the concrete behavior was asked and remains unresolved; they
are not a shortcut around the behavior interview.

## Mock Defaults

Do not ask the developer to choose implementation architecture during profiling.
The generator always creates typed operation controller TODOs. Ask only concrete
behavior questions needed to implement those controllers and feature modules
later: state changes, response bodies, IDs, timestamps, errors, auth simulation,
seed data, and edge cases. OpenAPI examples are schema examples, not seed
policy, unless nearby repository evidence clearly uses them as mock seed data.
If the user explicitly asks for empty initial product data, record
`state.seed = false` in `.mockapi/profile.toml`; otherwise leave it omitted or
set it to `true`. Missing seed examples are not an empty-seed opt-out.

For create operations, counter-based IDs are the default mock behavior. When
behavior says an operation creates generated, sequential, prefixed, or
counter-based IDs, include the `idCounters` singleton state slice in
`profile.toml`. Do not infer slug-style, name-derived, or title-derived IDs
from examples, titles, or request names; record that policy only when the
developer explicitly confirms it or repository evidence makes it product
behavior.

When profiling state slices, set `recordType` to the matching product schema
name when there is one API. If multiple APIs are configured, add
`schemaRef = "<api-name>#/components/schemas/<SchemaName>"` so admin state
generation can render typed mock-admin contracts without guessing. Use local
OpenAPI files for typed state schemas; remote HTTP OpenAPI inputs can still be
used for routes, but not for copied admin state schema components.
If the product schema is defined in a domain file rather than exported from the
root OpenAPI file, use
`schemaRef = "<api-name>:./relative-file.yaml#/components/schemas/<SchemaName>"`;
the file path is relative to the directory containing `apis[].openapi`.

## Source Order

Use this file, `reference/sidecars.md`, the OpenAPI contract, and nearby
repository context as the profiling sources of truth. During normal `profile`
work, do not read generator source to discover profiling requirements, accepted
TOML fields, defaults, validator expectations, or generation behavior.

If the reference docs do not define a concrete sidecar shape needed to finish
the profile, stop and state the exact missing fact as a skill documentation gap.
Do not inspect implementation artifacts to infer the shape. Python source
inspection is only for diagnosing validator or generator failures after
sidecars exist, not for authoring sidecar schema.

## Operation Rules

Use `## operation:<operationId>` for every operation. Record inferred behavior
for trivial operations, user-confirmed behavior for answered non-trivial
operations, or explicit open questions in `.mockapi/behavior.md`.
