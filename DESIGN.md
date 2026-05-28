<!-- SEED: re-run /impeccable document once there's code to capture the actual tokens and components. -->
---
name: mockapi
description: Stateful mock API servers from OpenAPI contracts.
---

# Design System: mockapi

## 1. Overview

**Creative North Star: "The Verification Workbench"**

The system should feel like a focused review surface for agent-built API mocks: clear enough for a human to audit, structured enough for an agent to continue, and restrained enough that contract, behavior, and validation stay in front. The physical scene is a developer reviewing OpenAPI contracts, sidecars, and generated behavior during normal daytime work on a laptop or external monitor.

The default theme is a light workbench, not a glossy launch page and not a raw terminal. It should borrow the crisp product confidence of Linear, Raycast, and Stripe docs without copying their branding. Every visual decision should support the product promise from `PRODUCT.md`: contract-first generation, traceable behavior, validation, and clean handoff between generated and human-owned code.

It explicitly rejects generic SaaS gloss: vague AI promises, decorative dashboard visuals, gradient-heavy hero treatments, oversized metric blocks, and interfaces that imply magic instead of showing the contract, behavior, and validation path.

**Key Characteristics:**
- Precise, practical, durable.
- Light, calm, and review-oriented.
- Dense enough for developer workflows, never cluttered for effect.
- Agent-readable and human-auditable.
- State is visible through structure, labels, and validation, not decoration.

## 2. Colors

The seed palette is restrained graphite neutrals with a muted verdigris accent. Exact values are to be resolved during implementation after a real UI surface exists.

### Primary
- **Workbench Verdigris** ([to be resolved during implementation]): Use sparingly for primary actions, current selection, valid progress, and the few moments where the interface needs to say "this path is ready."

### Neutral
- **Graphite Text** ([to be resolved during implementation]): Main text, headings, operation names, and durable labels.
- **Soft Workbench Surface** ([to be resolved during implementation]): Default page and panel background for the light review theme.
- **Quiet Rule Line** ([to be resolved during implementation]): Dividers, borders, inactive control outlines, and separation between generated and human-owned regions.
- **Muted Console Ink** ([to be resolved during implementation]): Secondary text, helper copy, metadata, and non-primary code-adjacent labels.

### Named Rules

**The Restrained Signal Rule.** Accent color is used only for primary action, current selection, focus, and state. If more than 10% of a normal product screen is accent-colored, the screen is shouting.

**The No-Magic Palette Rule.** Color must clarify workflow state or ownership. It must never imply automation magic, decorative intelligence, or generic AI SaaS energy.

## 3. Typography

**Display Font:** [font pairing to be chosen at implementation]
**Body Font:** [font pairing to be chosen at implementation]
**Label/Mono Font:** [mono family to be chosen at implementation]

**Character:** Use a single technical sans direction across product UI, docs-like explanation, labels, and dense controls. Mono is reserved for code, paths, operations, IDs, sidecar anchors, generated filenames, and values that benefit from exact scanning.

### Hierarchy
- **Display** ([to be resolved during implementation]): Rare. Use for top-level product or workflow titles only.
- **Headline** ([to be resolved during implementation]): Section-level orientation for setup, profiling, generation, validation, and review.
- **Title** ([to be resolved during implementation]): Panel titles, table group names, operation groups, and focused task headers.
- **Body** ([to be resolved during implementation]): Explanatory copy, guidance, and review notes. Keep prose lines readable, roughly 65-75 characters where layout allows.
- **Label** ([to be resolved during implementation]): Buttons, status labels, field labels, tabs, filters, and metadata. Labels should be compact and direct.
- **Code / Mono** ([to be resolved during implementation]): OpenAPI paths, operation IDs, sidecar anchors, package paths, endpoint names, and generated symbols.

### Named Rules

**The One Sans Rule.** Product UI does not need a display/body pairing. Use one precise sans direction until a real implementation proves otherwise.

**The Mono Is Evidence Rule.** Mono marks evidence: paths, IDs, routes, anchors, and generated names. It is not a decoration style.

## 4. Elevation

The seed system is flat by default and uses tonal layering, borders, and spacing before shadows. Shadows are allowed only when a surface changes state or needs to separate a temporary layer from the workbench, such as a command menu, popover, tooltip, or focused review panel.

### Named Rules

**The Flat-By-Default Rule.** Resting surfaces are flat. Depth appears as a response to state, not as a decorative baseline.

**The Evidence Over Atmosphere Rule.** If a shadow makes a generated artifact look more important than the contract or validation result, remove it.

## 6. Do's and Don'ts

### Do:
- **Do** make contract, behavior, validation, and ownership boundaries visually obvious.
- **Do** keep the interface calm enough for repeated review work.
- **Do** use muted verdigris only for action, focus, selection, valid state, and progress.
- **Do** reserve mono treatment for exact technical evidence: routes, paths, IDs, sidecar anchors, and generated symbols.
- **Do** support keyboard access, visible focus, reduced motion preferences, and status communication that does not rely on color alone.
- **Do** favor clear state labels, inline validation, and structured repair paths over modal-heavy interruptions.

### Don't:
- **Don't** use generic SaaS gloss: vague AI promises, decorative dashboard visuals, gradient-heavy hero treatments, oversized metric blocks, or interfaces that imply magic instead of showing the contract, behavior, and validation path.
- **Don't** use generic AI SaaS pages as a visual model: no purple gradients, hero metrics, vague automation promises, or decorative dashboard screenshots.
- **Don't** make future product surfaces feel like a marketing template, a toy demo, or an opaque code generator.
- **Don't** default to bare CLI austerity when structured review, state inspection, or guided repair would help.
- **Don't** use side-stripe borders, gradient text, decorative glassmorphism, identical card grids, or modal-first flows.
- **Don't** add decorative motion. Motion is for focus, hover, loading, validation, and state changes in the 150-200 ms range.
