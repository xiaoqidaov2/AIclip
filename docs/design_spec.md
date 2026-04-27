# AiClip Design Spec

## Goal
- Build an AI-assisted video editing CLI that can edit, analyze, render, and iterate on a project from raw media.
- Keep the system autonomous by default, while allowing explicit planning and clarification when the model judges it useful.

## Current Shape
- Entry point: `main.py`
- CLI layer: `src/cli/`
- LLM routing and orchestration: `src/llm/`
- Editing core and project model: `src/editor_core/`
- Media and external asset tools: `src/net_asset/`
- Shared tool docs and skill notes: `resources/docs/` and `resources/skills/`

## Core Boundaries
- The agent should not depend on hard-coded human confirmation gates.
- Planning is optional and should be invoked by agent judgment or explicit user request.
- A plan is not an execution lock.
- Tool output is the source of truth for progress and state.
- Tool `next_actions` must remain descriptive metadata, not an automatic execution trigger.

## Proposed Agent Split
- Router Agent: intent classification and initial path selection.
- Editor Agent: project changes, subtitle fixes, timing, effects, cuts.
- Reviewer Agent: video inspection, quality scoring, issue detection.
- Clarifier Agent: ask up to 5 questions when the model lacks enough context.
- Render Agent: final export and render validation.

## Configuration Principles
- Agent roles, prompts, tool permissions, and handoff rules should live in external config.
- Code should load config rather than embed role-specific prompt logic.
- Prompt text should be versioned separately from implementation.
- Skill definitions should remain data-driven via `resources/skills/skills.json`.

## Interaction Rules
- Default path: direct execution when the model has sufficient context.
- Planning path: used only when uncertainty, ambiguity, or branching risk is material.
- Clarification path: used when the model needs user input before editing.
- User can request `/plan` to inspect intent without forcing the system into a plan-first workflow.

## Clarification Rules
- Max 5 questions.
- Max 5 choices per question.
- Every question must include one free-text option.
- Questions should be bundled into one compact interaction surface.
- Avoid repeated follow-up prompts unless the model still lacks required context.

## Non-Goals
- Do not hard-code a mandatory `plan -> run` gate.
- Do not force the user through confirmation steps for routine edits.
- Do not bake human guidance into execution rules that override model reasoning.
- Do not auto-advance tool chains solely because a tool returned `next_actions`.

## Existing Useful Pieces
- Skill registry already lives in `resources/skills/skills.json`.
- Tool docs already live in `resources/docs/`.
- The CLI already supports structured session state and skill switching.
- The project already has separate vision and project-core tool surfaces.

## Risks
- Over-splitting agents can increase orchestration overhead.
- Too much prompt logic in code will make role changes hard to maintain.
- Aggressive auto-flow removal can reduce convenience if no explicit execute command remains.

## Recommendation
- Keep a fast default direct-execute path.
- Introduce optional planning and clarification as agent-driven tools, not mandatory UI steps.
- Move role prompts and routing policy into config files before adding more agent types.
