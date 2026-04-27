# AiClip Development Plan TODO

## Phase 1: Architecture
- [ ] Define final agent roster and responsibilities.
- [ ] Decide which agents are always available and which are optional.
- [ ] Define handoff contracts between router, planner, clarifier, reviewer, editor, and renderer.
- [ ] Freeze the execution boundary: what can auto-run and what must be explicitly requested.

## Phase 2: Configuration Externalization
- [ ] Move agent system prompts into config files.
- [ ] Move tool allowlists into config files.
- [ ] Move handoff rules and default policies into config files.
- [ ] Add config loading and validation.

## Phase 3: CLI Interaction
- [ ] Add a compact clarification UI for multi-question prompts.
- [ ] Support up to 5 questions with up to 5 choices each.
- [ ] Add a free-text option to every question.
- [ ] Keep the default interaction path fast and non-blocking.

## Phase 4: Orchestration
- [ ] Refactor orchestration to support explicit plan generation without forcing execution.
- [ ] Remove any remaining auto-advance semantics from `next_actions`.
- [ ] Add explicit execution entrypoints only if needed by the UX.
- [ ] Make reviewer-driven iteration a model choice, not a hard-coded loop.

## Phase 5: Skills and Tools
- [ ] Split `project_core` into narrower responsibilities if the config model needs it.
- [ ] Revisit `vision_inspection` boundaries and output schema.
- [ ] Document each agent's tool surface clearly.
- [ ] Ensure subtitle correction, render prep, and export are separately testable.

## Phase 6: Testing
- [ ] Add tests for plan-only behavior.
- [ ] Add tests for clarification bundle generation.
- [ ] Add tests for config-driven agent loading.
- [ ] Add regression tests that guard against hidden auto-execution.

## Phase 7: Documentation
- [ ] Update README with the new agent model.
- [ ] Update skill docs to match the split responsibilities.
- [ ] Add examples showing direct execution vs plan vs clarification.
- [ ] Record edge cases and operator guidance.
