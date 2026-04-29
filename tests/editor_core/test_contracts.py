from dataclasses import dataclass


from src.editor_core.contracts import (
    ArtifactRef,
    RenderState,
    ToolChange,
    ToolResult,
    ValidationSnapshot,
    normalize_tool_result,
    serialize_tool_result,
)


def test_tool_result_to_dict_populates_summary_and_decision_defaults():

    # compact mode (default): summary omitted when == message, decision omitted
    result = ToolResult(
        ok=True,
        status="ok",
        code="demo.ok",
        message="done",
        operation="demo",
        validation=ValidationSnapshot(passed=True, warnings=["w"]),
        render_state=RenderState(ready=True),
    ).to_dict()

    assert "summary" not in result  # omitted because it equals message
    assert result["operation"] == "demo"
    assert result["validation"]["warnings"] == ["w"]
    assert "decision" not in result  # omitted in compact mode

    # non-compact mode: summary and decision are present
    full = ToolResult(
        ok=True,
        status="ok",
        code="demo.ok",
        message="done",
        operation="demo",
        validation=ValidationSnapshot(passed=True, warnings=["w"]),
        render_state=RenderState(ready=True),
    ).to_dict(compact=False)

    assert full["summary"] == "done"
    assert full["decision"]["ok"] is True


def test_tool_result_to_dict_does_not_merge_payload_keys():

    payload = {"output_path": "out.mp4", "message": "custom"}

    result = ToolResult(
        ok=True,
        status="ok",
        code="x.ok",
        message="base",
        operation="x",
        payload=payload,
    ).to_dict()

    assert result["payload"]["output_path"] == "out.mp4"

    assert result["message"] == "base"


def test_normalize_tool_result_for_already_normalized_dict_infers_ok():

    raw = {"status": "failed", "code": "x.failed", "message": "nope"}

    normalized = normalize_tool_result("operation_x", raw)

    assert normalized["ok"] is False

    assert normalized["status"] == "failed"

    assert normalized["operation"] == "operation_x"


def test_normalize_tool_result_for_generic_dict_normalizes_nested_fields():

    raw = {
        "status": "ok",
        "message": "updated",
        "changes": {"type": "asset", "id": "a1", "field": "assets"},
        "validation": {"passed": False, "warnings": "warn", "errors": ["e1"]},
        "render_state": {"ready": True, "blockers": "none"},
        "artifacts": {"type": "file", "path": "/tmp/x"},
        "next_actions": "render",
        "state": {"existing": 1},
        "output_path": "/tmp/out",
    }

    normalized = normalize_tool_result("update_asset", raw, entity="asset")

    assert normalized["operation"] == "update_asset"

    assert normalized["changes"][0]["id"] == "a1"

    assert normalized["validation"]["errors"] == ["e1"]

    assert normalized["render_state"]["ready"] is True

    assert normalized["artifacts"][0]["path"] == "/tmp/x"

    assert normalized["state"]["output_path"] == "/tmp/out"

    # decision is omitted in compact mode; check via non-compact
    full = normalize_tool_result("update_asset", raw, entity="asset", compact=False)
    assert full["decision"]["ok"] is True


def test_normalize_tool_result_accepts_dataclass_instances():

    @dataclass
    class Raw:

        status: str = "ok"

        code: str = "raw.ok"

        message: str = "raw message"

    normalized = normalize_tool_result("raw_op", Raw())

    assert normalized["code"] == "raw.ok"

    assert normalized["operation"] == "raw_op"


def test_normalize_tool_result_for_scalar_payload():

    normalized = normalize_tool_result(
        "describe", "plain text", project_id="p1", project_version=3
    )

    assert normalized["ok"] is True

    assert normalized["project_id"] == "p1"

    assert normalized["project_version"] == 3

    # decision omitted in compact mode
    assert "decision" not in normalized

    # non-compact mode includes decision
    full = normalize_tool_result("describe", "plain text", project_id="p1", project_version=3, compact=False)
    assert full["decision"]["ok"] is True


def test_serialize_tool_result_returns_json_string():

    output = serialize_tool_result(
        "op", {"status": "ok", "code": "op.ok", "message": "m"}
    )

    assert '"code": "op.ok"' in output


def test_normalize_tool_result_handles_pretyped_components():

    raw = {
        "status": "ok",
        "message": "done",
        "changes": [ToolChange(type="clip", id="c1", field="speed")],
        "validation": ValidationSnapshot(passed=True),
        "render_state": RenderState(ready=True),
        "artifacts": [ArtifactRef(type="file", path="p")],
    }

    normalized = normalize_tool_result("op", raw)

    assert normalized["changes"][0]["type"] == "clip"

    # validation passed with no warnings/errors → omitted in compact mode
    assert "validation" not in normalized

    # render_state ready with no blockers → omitted in compact mode
    assert "render_state" not in normalized

    assert normalized["artifacts"][0]["path"] == "p"

    # non-compact mode keeps validation and render_state
    full = normalize_tool_result("op", raw, compact=False)
    assert full["validation"]["passed"] is True
    assert full["render_state"]["ready"] is True
