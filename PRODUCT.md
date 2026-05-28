# Product

## Register

product

## Users

Agent builders who use agent-invoked skills and workflows to turn OpenAPI contracts into realistic local mock APIs. They work across product, frontend, backend, and QA contexts, and need the agent to preserve decisions across profiling, generation, repair, and review.

## Product Purpose

`mockapi` generates stateful TypeScript/Hono mock API servers from OpenAPI 3.0 and 3.1 contracts. It exists to make realistic local APIs reliable enough for real product workflows without hand-writing one-off mock servers.

Success means a user can profile an API contract, capture durable behavior in sidecars, generate a runnable server, inspect and reset state through admin endpoints, and safely regenerate infrastructure without losing human-owned behavior.

## Brand Personality

Precise, practical, durable.

The product should feel like expert developer infrastructure: direct, calm, legible, and trustworthy. It should avoid inflated claims and should make constraints visible instead of hiding them behind polish.

## Anti-references

Avoid generic SaaS gloss: vague AI promises, decorative dashboard visuals, gradient-heavy hero treatments, oversized metric blocks, and interfaces that imply magic instead of showing the contract, behavior, and validation path.

Do not make future product surfaces feel like a marketing template, a toy demo, or an opaque code generator. The experience should also avoid bare CLI austerity when a user needs structured review, state inspection, or guided repair.

## Design Principles

Contract first. OpenAPI remains the source of route truth, and every product surface should make that relationship obvious.

Make behavior traceable. Sidecars, behavior anchors, generated files, and feature code should be easy to connect mentally.

Earn trust through validation. Checks, errors, and repair paths should be specific, calm, and actionable.

Keep ownership boundaries clear. Generated infrastructure, durable sidecars, and reviewable feature behavior should never blur together.

Optimize for agent-human handoff. Interfaces and copy should help an agent continue work while leaving enough structure for a human to audit decisions quickly.

## Accessibility & Inclusion

Target WCAG 2.2 AA for future UI work. Support keyboard access, visible focus states, reduced motion preferences, sufficient contrast, and status communication that does not rely on color alone.
