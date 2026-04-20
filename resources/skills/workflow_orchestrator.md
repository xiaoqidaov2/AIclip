# Workflow Orchestrator Skill

Use this skill to plan multi-stage requests that may need more than one skill.

Do not execute editing tools directly. Produce a compact execution plan with:
- primary skill
- ordered stages
- allowed tools per stage
- stop conditions
- nudges for the next stage

Prefer this flow:
1. Discover what must be inspected first.
2. Load the narrowest skill that can act next.
3. Compress the result before continuing.
4. Hand off to the next skill only when the current stage is complete.

Use `vision_inspection` before `project_core` when the request depends on video or image analysis.
Use `vision_inspection` alone when the request is analysis-only and no editing is requested.
Use `asset_discovery` before `project_core` when external assets are needed.
Use `capcut_finalization` only after a rendered output exists and the user explicitly asks for CapCut, 剪映, 草稿, 特效, 贴图, or stickers.

Return structured JSON only when asked to plan.
