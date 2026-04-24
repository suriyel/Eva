"""F18 · Bk-Adapter — Coverage supplement tests.

Quality-gate coverage gap补测。目标：让 harness/ line ≥90% / branch ≥80%。
feature: 18 (Bk-Adapter — Agent Adapter & HIL Pipeline).

策略（与 feature design §4 / §6 对齐）：
  - harness/stream/parser.py  : 多 chunk / 空 chunk / async events() EOF / non-dict / unknown kind
  - harness/hil/extractor.py  : 非 tool_use / 非 HIL 名称 / options 非 list / 非 dict entry / 截断
  - harness/hil/event_bus.py  : publish_answered / broadcast-only / audit-only 路径
  - harness/adapter/claude.py : parse_result / detect_anomaly 多分类 / supports flags / _sanitise_env
  - harness/adapter/opencode/__init__.py : build_argv 各分支 / detect_anomaly / supports / extract_hil / parse_result
  - harness/adapter/opencode/hooks.py   : HookQuestionParser 非 JSON / 非 dict / 缺 channel / name 截断
  - harness/pty/worker.py     : write/close 幂等 / crashed 状态 / PtyClosedError re-raise

Layer marker:
  # [unit] — 无 real subprocess；Rule 5a 未违反（不 mock primary deps）。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness.domain.ticket import DispatchSpec


def _isolated_spec(tmp_path, **overrides):
    """Common isolated DispatchSpec factory for coverage tests."""
    base = tmp_path / ".harness-workdir" / "r1"
    plugin_dir = base / ".claude" / "plugins"
    settings_path = base / ".claude" / "settings.json"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{}")
    kwargs = dict(
        argv=["claude"],
        env={"PATH": "/usr/bin"},
        cwd=str(base),
        model=None,
        mcp_config=None,
        plugin_dir=str(plugin_dir),
        settings_path=str(settings_path),
    )
    kwargs.update(overrides)
    return DispatchSpec(**kwargs)


# ---------------------------------------------------------------------------
# harness/stream/parser.py — edge branches
# ---------------------------------------------------------------------------


def test_parser_empty_chunk_returns_empty_list():
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    assert parser.feed(b"") == []


def test_parser_non_dict_json_is_skipped(caplog):
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    with caplog.at_level(logging.WARNING):
        events = parser.feed(b"[1,2,3]\n")
    assert events == []
    assert any("non-object" in rec.getMessage().lower() for rec in caplog.records)


def test_parser_unknown_kind_coerced_to_system(caplog):
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    with caplog.at_level(logging.WARNING):
        events = parser.feed(b'{"type":"heartbeat","payload":{"x":1}}\n')
    assert len(events) == 1
    assert events[0].kind == "system"


def test_parser_seq_non_int_falls_back_to_zero():
    """seq 非 int → int(... ) 引发 ValueError 分支 → seq=0."""
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    events = parser.feed(b'{"type":"text","seq":"abc","text":"x"}\n')
    assert len(events) == 1
    assert events[0].seq == 0


def test_parser_blank_lines_skipped():
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    events = parser.feed(b'\n   \n{"type":"text","text":"a"}\n')
    assert len(events) == 1
    assert events[0].kind == "text"


def test_parser_reset_for_test_clears_buffer():
    from harness.stream.parser import JsonLinesParser

    parser = JsonLinesParser()
    parser.feed(b'{"type":"text",')  # incomplete → goes to buffer
    parser._reset_for_test()
    # After reset the next complete chunk should parse cleanly.
    events = parser.feed(b'{"type":"text","text":"a"}\n')
    assert len(events) == 1


@pytest.mark.asyncio
async def test_parser_events_iterates_queue_until_eof_sentinel():
    """async events() — EOF via sentinel None yields ErrorEvent then stops."""
    from harness.stream.parser import JsonLinesParser

    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(b'{"type":"text","text":"a"}\n')
    await queue.put(b'{"type":"system","session_id":"s1"}\n')
    await queue.put(None)  # EOF

    parser = JsonLinesParser()
    collected = []
    async for evt in parser.events(queue):
        collected.append(evt)

    # Expect 2 real events + 1 synthetic error event for EOF.
    assert len(collected) == 3
    assert collected[-1].kind == "error"
    assert "pty_eof" in str(collected[-1].payload)


# ---------------------------------------------------------------------------
# harness/hil/extractor.py — edge branches
# ---------------------------------------------------------------------------


def test_extractor_ignores_non_tool_use_event():
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(kind="text", seq=1, payload={"text": "hello"})
    assert HilExtractor().extract(evt) == []


def test_extractor_ignores_non_hil_tool_name():
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(kind="tool_use", seq=1, payload={"name": "Read", "input": {}})
    assert HilExtractor().extract(evt) == []


def test_extractor_questions_not_a_list_warns_and_returns_empty(caplog):
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={"name": "AskUserQuestion", "input": {"questions": "not-a-list"}},
    )
    with caplog.at_level(logging.WARNING):
        result = HilExtractor().extract(evt)
    assert result == []
    assert any("list" in rec.getMessage().lower() for rec in caplog.records)


def test_extractor_skips_non_dict_question_entry(caplog):
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "Question",
            "input": {"questions": ["bogus-string-entry", {"header": "h", "question": "q"}]},
        },
    )
    with caplog.at_level(logging.WARNING):
        result = HilExtractor().extract(evt)
    # Only the dict entry normalises; bogus string skipped with warning.
    assert len(result) == 1
    assert any("non-dict" in rec.getMessage().lower() for rec in caplog.records)


def test_extractor_options_non_list_coerced_to_empty(caplog):
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "AskUserQuestion",
            "input": {
                "questions": [
                    {"header": "h", "question": "q", "options": "not-a-list"},
                ]
            },
        },
    )
    with caplog.at_level(logging.WARNING):
        result = HilExtractor().extract(evt)
    assert len(result) == 1
    assert result[0].options == []


def test_extractor_truncates_header_over_256_bytes():
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    long_header = "A" * 300
    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "AskUserQuestion",
            "input": {"questions": [{"header": long_header, "question": "q", "options": []}]},
        },
    )
    result = HilExtractor().extract(evt)
    assert len(result) == 1
    # Body should include the ellipsis suffix and be ≤ 256 + len(ellipsis) bytes.
    assert result[0].header.endswith("…")
    assert len(result[0].header.encode("utf-8")) <= 256 + len("…".encode("utf-8"))


def test_extractor_option_description_preserved_and_truncated():
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "AskUserQuestion",
            "input": {
                "questions": [
                    {
                        "header": "h",
                        "question": "q",
                        "options": [
                            {"label": "x", "description": "B" * 300},
                            {"label": "plain"},
                            "scalar-option-not-dict",
                        ],
                    }
                ]
            },
        },
    )
    result = HilExtractor().extract(evt)
    assert len(result) == 1
    opts = result[0].options
    assert len(opts) == 3
    assert opts[0].description is not None
    assert opts[0].description.endswith("…")
    assert opts[1].description is None
    # Scalar non-dict entry still yields an option with stringified label.
    assert opts[2].label == "scalar-option-not-dict"


def test_extractor_uses_id_from_payload_when_present():
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "AskUserQuestion",
            "input": {
                "questions": [
                    {
                        "id": "provided-id-123",
                        "header": "h",
                        "question": "q",
                        "options": [],
                        "allowFreeformInput": True,
                    }
                ]
            },
        },
    )
    result = HilExtractor().extract(evt)
    assert result[0].id == "provided-id-123"
    assert result[0].kind == "free_text"


def test_extractor_snake_case_fields_also_recognised():
    """OpenCode shape uses snake_case (multi_select / allow_freeform)."""
    from harness.hil.extractor import HilExtractor
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "Question",
            "input": {
                "questions": [
                    {
                        "title": "use title alias",
                        "prompt": "use prompt alias",
                        "options": [{"label": "a"}, {"label": "b"}],
                        "multi_select": True,
                        "allow_freeform": False,
                    }
                ]
            },
        },
    )
    result = HilExtractor().extract(evt)
    assert result[0].header == "use title alias"
    assert result[0].question == "use prompt alias"
    assert result[0].multi_select is True
    assert result[0].kind == "multi_select"


# ---------------------------------------------------------------------------
# harness/hil/event_bus.py — publish paths
# ---------------------------------------------------------------------------


class _CaptureAudit:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)


def test_event_bus_publish_answered_appends_audit_and_broadcasts():
    from harness.domain.ticket import HilAnswer
    from harness.hil.event_bus import HilEventBus

    audit = _CaptureAudit()
    broadcasts = []
    bus = HilEventBus(ws_broadcast=broadcasts.append, audit=audit)

    ans = HilAnswer(
        question_id="q1",
        selected_labels=["yes"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    bus.publish_answered(ticket_id="t1", run_id="r1", answer=ans)

    assert len(audit.events) == 1
    assert audit.events[0].event_type == "hil_answered"
    assert len(broadcasts) == 1
    assert "yes" in json.dumps(broadcasts[0])


def test_event_bus_publish_without_audit_still_broadcasts():
    """audit=None path must not raise (cov 47->57 / 67->exit branches)."""
    from harness.domain.ticket import HilAnswer, HilOption, HilQuestion
    from harness.hil.event_bus import HilEventBus

    broadcasts = []
    bus = HilEventBus(ws_broadcast=broadcasts.append, audit=None)

    q = HilQuestion(
        id="q1",
        kind="single_select",
        header="h",
        question="q",
        options=[HilOption(label="x")],
        multi_select=False,
        allow_freeform=False,
    )
    bus.publish_opened(ticket_id="t1", run_id="r1", question=q)

    ans = HilAnswer(
        question_id="q1",
        selected_labels=["x"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    bus.publish_answered(ticket_id="t1", run_id="r1", answer=ans)

    assert len(broadcasts) == 2


def test_event_bus_audit_only_path_no_broadcast():
    """ws_broadcast=None path must not raise (57->exit branch)."""
    from harness.domain.ticket import HilAnswer, HilOption, HilQuestion
    from harness.hil.event_bus import HilEventBus

    audit = _CaptureAudit()
    bus = HilEventBus(ws_broadcast=None, audit=audit)

    q = HilQuestion(
        id="q1",
        kind="single_select",
        header="h",
        question="q",
        options=[HilOption(label="x")],
    )
    bus.publish_opened(ticket_id="t1", run_id="r1", question=q)
    ans = HilAnswer(
        question_id="q1",
        selected_labels=["x"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    bus.publish_answered(ticket_id="t1", run_id="r1", answer=ans)

    assert len(audit.events) == 2


# ---------------------------------------------------------------------------
# harness/adapter/claude.py — parse_result / detect_anomaly / supports / env
# ---------------------------------------------------------------------------


def test_claude_parse_result_concats_text_and_extracts_session_id():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(kind="text", seq=1, payload={"text": "hello "}),
        StreamEvent(kind="text", seq=2, payload={"text": "world"}),
        StreamEvent(kind="system", seq=3, payload={"session_id": "sess-123"}),
        # tool_use ignored by parse_result
        StreamEvent(kind="tool_use", seq=4, payload={"name": "X"}),
    ]
    out = ClaudeCodeAdapter().parse_result(events)
    assert out.result_text == "hello world"
    assert out.session_id == "sess-123"


def test_claude_parse_result_session_id_camelcase_variant():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="system", seq=1, payload={"sessionId": "alt-999"})]
    out = ClaudeCodeAdapter().parse_result(events)
    assert out.session_id == "alt-999"
    assert out.result_text is None


def test_claude_parse_result_text_non_string_ignored():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="text", seq=1, payload={"text": 42})]
    out = ClaudeCodeAdapter().parse_result(events)
    assert out.result_text is None


def test_claude_parse_result_empty_events_returns_empty_output():
    from harness.adapter.claude import ClaudeCodeAdapter

    out = ClaudeCodeAdapter().parse_result([])
    assert out.result_text is None
    assert out.session_id is None


@pytest.mark.parametrize(
    "needle,expected",
    [
        ("context length exceeded", "context_overflow"),
        ("rate limited now", "rate_limit"),
        ("EHOSTUNREACH peer unreachable", "network"),
        ("operation timeout hit", "timeout"),
        ("SIGSEGV crash", "skill_error"),
        ("unexpected EOF detected", "skill_error"),
    ],
)
def test_claude_detect_anomaly_all_classifications(needle, expected):
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="error", seq=1, payload={"message": needle})]
    info = ClaudeCodeAdapter().detect_anomaly(events)
    assert info is not None
    assert info.cls == expected


def test_claude_detect_anomaly_returns_none_when_no_match():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    # text events should be skipped (not error/system) — kind filter branch.
    events = [
        StreamEvent(kind="text", seq=1, payload={"text": "rate limited but wrong kind"}),
        StreamEvent(kind="error", seq=2, payload={"message": "benign"}),
    ]
    assert ClaudeCodeAdapter().detect_anomaly(events) is None


def test_claude_detect_anomaly_reads_text_field_on_system_event():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="system", seq=1, payload={"text": "rate limited"})]
    info = ClaudeCodeAdapter().detect_anomaly(events)
    assert info is not None and info.cls == "rate_limit"


def test_claude_supports_flags():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.adapter.protocol import CapabilityFlags

    a = ClaudeCodeAdapter()
    assert a.supports(CapabilityFlags.MCP_STRICT) is True
    assert a.supports(CapabilityFlags.HOOKS) is False


def test_claude_extract_hil_non_tool_use_returns_empty():
    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.stream.events import StreamEvent

    adapter = ClaudeCodeAdapter()
    evt = StreamEvent(kind="text", seq=1, payload={"text": "hi"})
    assert adapter.extract_hil(evt) == []


def test_claude_sanitise_env_only_whitelisted_vars_survive():
    from harness.adapter.claude import ClaudeCodeAdapter

    sanitised = ClaudeCodeAdapter._sanitise_env(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "CLAUDE_CONFIG_DIR": "/tmp/isolated",
            "SECRET_KEY": "should-be-dropped",
            "AWS_ACCESS_KEY_ID": "should-be-dropped",
        }
    )
    assert "PATH" in sanitised
    assert "HOME" in sanitised
    assert "CLAUDE_CONFIG_DIR" in sanitised
    assert "SECRET_KEY" not in sanitised
    assert "AWS_ACCESS_KEY_ID" not in sanitised


def test_claude_default_factory_returns_callable_on_posix():
    """Covers the _default_factory posix branch (lines 223-226)."""
    import os as _os

    from harness.adapter.claude import ClaudeCodeAdapter

    if _os.name != "posix":
        pytest.skip("posix branch only")
    factory = ClaudeCodeAdapter._default_factory()
    # Factory must be a callable class ref; construct it and verify shape.
    inst = factory(["echo"], {"PATH": "/usr/bin"}, "/tmp")
    assert hasattr(inst, "start") and hasattr(inst, "read") and hasattr(inst, "write")


def test_claude_build_argv_with_model_and_mcp():
    """Strict-order argv (T02 checks model; T01 checks mcp) — exercise both."""
    from harness.adapter.claude import ClaudeCodeAdapter

    tmp = Path("/tmp/.harness-workdir/r-cov1")
    tmp.mkdir(parents=True, exist_ok=True)
    pd = tmp / ".claude" / "plugins"
    sp = tmp / ".claude" / "settings.json"
    pd.mkdir(parents=True, exist_ok=True)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{}")
    mcp = tmp / "mcp.json"
    mcp.write_text("{}")

    spec = DispatchSpec(
        argv=["claude"],
        env={"PATH": "/usr/bin"},
        cwd=str(tmp),
        model="sonnet-4",
        mcp_config=str(mcp),
        plugin_dir=str(pd),
        settings_path=str(sp),
    )
    argv = ClaudeCodeAdapter().build_argv(spec)
    assert "--model" in argv and "sonnet-4" in argv
    assert "--mcp-config" in argv and "--strict-mcp-config" in argv
    assert "-p" not in argv


# ---------------------------------------------------------------------------
# harness/adapter/opencode/__init__.py — branches
# ---------------------------------------------------------------------------


def test_opencode_build_argv_minimal_only_binary_name():
    from harness.adapter.opencode import OpenCodeAdapter

    spec = _isolated_spec(
        tmp_path=Path("/tmp"),
        argv=["opencode"],
    )
    # _isolated_spec drops files into /tmp/.harness-workdir/r1 which is fine here.
    argv = OpenCodeAdapter().build_argv(spec)
    assert argv == ["opencode"]


def test_opencode_build_argv_with_model(tmp_path):
    from harness.adapter.opencode import OpenCodeAdapter

    spec = _isolated_spec(tmp_path, argv=["opencode"], model="gpt-4o-mini")
    argv = OpenCodeAdapter().build_argv(spec)
    assert argv == ["opencode", "--model", "gpt-4o-mini"]


def test_opencode_build_argv_mcp_drops_flag_and_toasts(tmp_path):
    from harness.adapter.opencode import OpenCodeAdapter

    mcp = tmp_path / "mcp.json"
    mcp.write_text("{}")
    spec = _isolated_spec(tmp_path, argv=["opencode"], mcp_config=str(mcp))
    adapter = OpenCodeAdapter()
    argv = adapter.build_argv(spec)
    assert "--mcp-config" not in argv
    assert "--strict-mcp-config" not in argv
    assert adapter.mcp_degrader.toast_pushed is True
    assert any("MCP" in m for m in adapter.mcp_degrader.messages)


def test_opencode_supports_flags():
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.adapter.protocol import CapabilityFlags

    a = OpenCodeAdapter()
    assert a.supports(CapabilityFlags.HOOKS) is True
    assert a.supports(CapabilityFlags.MCP_STRICT) is False


def test_opencode_extract_hil_delegates_to_shared_extractor():
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.stream.events import StreamEvent

    evt = StreamEvent(
        kind="tool_use",
        seq=1,
        payload={
            "name": "Question",
            "input": {"questions": [{"header": "h", "question": "q", "options": []}]},
        },
    )
    out = OpenCodeAdapter().extract_hil(evt)
    assert len(out) == 1


def test_opencode_parse_result_concatenates_text_events():
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(kind="text", seq=1, payload={"text": "hi "}),
        StreamEvent(kind="text", seq=2, payload={"text": "there"}),
        StreamEvent(kind="system", seq=3, payload={}),  # non-text ignored
        StreamEvent(kind="text", seq=4, payload={"text": 42}),  # non-str ignored
    ]
    out = OpenCodeAdapter().parse_result(events)
    assert out.result_text == "hi there"


def test_opencode_parse_result_empty():
    from harness.adapter.opencode import OpenCodeAdapter

    out = OpenCodeAdapter().parse_result([])
    assert out.result_text is None


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("Error: not authenticated", "skill_error"),
        ("context length exceeded", "context_overflow"),
        ("too many rate requests", "rate_limit"),
    ],
)
def test_opencode_detect_anomaly_classifications(msg, expected):
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="error", seq=1, payload={"message": msg})]
    info = OpenCodeAdapter().detect_anomaly(events)
    assert info is not None and info.cls == expected


def test_opencode_detect_anomaly_returns_none_when_no_match():
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(kind="text", seq=1, payload={"text": "not authenticated in text kind"}),
        StreamEvent(kind="error", seq=2, payload={"message": "benign"}),
    ]
    assert OpenCodeAdapter().detect_anomaly(events) is None


def test_opencode_ensure_hooks_empty_cwd_raises(tmp_path):
    from harness.adapter.errors import InvalidIsolationError
    from harness.adapter.opencode import OpenCodeAdapter
    from harness.env.models import IsolatedPaths

    paths = IsolatedPaths(
        cwd="",
        plugin_dir=str(tmp_path / "pd"),
        settings_path=str(tmp_path / "s.json"),
        mcp_config_path=None,
    )
    with pytest.raises(InvalidIsolationError):
        OpenCodeAdapter().ensure_hooks(paths)


def test_opencode_default_factory_returns_posix_pty_on_posix():
    import os as _os

    from harness.adapter.opencode import OpenCodeAdapter

    if _os.name != "posix":
        pytest.skip("posix branch only")
    factory = OpenCodeAdapter._default_factory()
    inst = factory(["echo"], {"PATH": "/usr/bin"}, "/tmp")
    assert hasattr(inst, "start")


def test_opencode_parse_version_edge_cases():
    """harness/adapter/opencode/__init__.py::_parse_version lines 66-69."""
    from harness.adapter.opencode import _parse_version

    # trim 'v' prefix and garbage chars -> digits only
    assert _parse_version("v1.2.3") == (1, 2, 3)
    assert _parse_version("1.2") == (1, 2, 0)
    assert _parse_version("") == (0, 0, 0)
    assert _parse_version("abc") == (0, 0, 0)
    # "1-beta2" -> digits join to "12" per current parse impl
    assert _parse_version("0.3.1-beta2") == (0, 3, 12)


def test_opencode_spawn_raises_when_too_old(tmp_path, monkeypatch):
    """Line 118-131 path: spawn → old version → HookRegistrationError."""
    from harness.adapter.errors import HookRegistrationError
    from harness.adapter.opencode import OpenCodeAdapter

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "harness.adapter.opencode.VersionCheck.current_version",
        staticmethod(lambda: "0.2.9"),
    )

    adapter = OpenCodeAdapter()
    spec = _isolated_spec(tmp_path, argv=["opencode"])
    with pytest.raises(HookRegistrationError) as exc:
        adapter.spawn(spec)
    assert "too old" in str(exc.value).lower() or "upgrade" in str(exc.value).lower()


def test_opencode_spawn_happy_path_with_fake_pty(tmp_path, monkeypatch):
    """Line 118-131 happy branch: version OK → pty_factory → TicketProcess returned."""
    from harness.adapter.opencode import OpenCodeAdapter

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "harness.adapter.opencode.VersionCheck.current_version",
        staticmethod(lambda: "0.5.0"),
    )

    captured = {}

    class FakePty:
        def __init__(self, argv, env, cwd):
            captured["argv"] = list(argv)
            captured["env"] = dict(env)
            captured["cwd"] = cwd
            self.pid = 77777

        def start(self):
            captured["started"] = True

        def write(self, data):
            return len(data)

        def close(self):
            captured["closed"] = True

    adapter = OpenCodeAdapter(pty_factory=FakePty)
    spec = _isolated_spec(tmp_path, argv=["opencode"])
    # Also stuff in non-whitelisted env var to hit the filter branch at line 118.
    spec = spec.model_copy(
        update={"env": {"PATH": "/usr/bin", "AWS_SECRET": "drop-me", "HOME": "/home/x"}}
    )
    proc = adapter.spawn(spec)
    assert proc.pid == 77777
    # Env filter must have dropped AWS_SECRET (line 118).
    assert "PATH" in captured["env"]
    assert "HOME" in captured["env"]
    assert "AWS_SECRET" not in captured["env"]


def test_opencode_spawn_cli_missing(tmp_path, monkeypatch):
    from harness.adapter.errors import SpawnError
    from harness.adapter.opencode import OpenCodeAdapter

    monkeypatch.setattr("shutil.which", lambda name: None)
    adapter = OpenCodeAdapter()
    spec = _isolated_spec(tmp_path, argv=["opencode"])
    with pytest.raises(SpawnError) as exc:
        adapter.spawn(spec)
    assert "not found" in str(exc.value).lower()


def test_opencode_spawn_pty_init_failure_wraps_spawn_error(tmp_path, monkeypatch):
    """Line 121-123 exception branch when pty_factory raises."""
    from harness.adapter.errors import SpawnError
    from harness.adapter.opencode import OpenCodeAdapter

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        "harness.adapter.opencode.VersionCheck.current_version",
        staticmethod(lambda: "0.5.0"),
    )

    def bad_factory(argv, env, cwd):
        raise OSError("factory kaboom")

    adapter = OpenCodeAdapter(pty_factory=bad_factory)
    spec = _isolated_spec(tmp_path, argv=["opencode"])
    with pytest.raises(SpawnError) as exc:
        adapter.spawn(spec)
    assert "PTY init failed" in str(exc.value)


def test_opencode_parse_hook_line_delegates(tmp_path):
    """Line 170-171: parse_hook_line delegation to HookQuestionParser."""
    from harness.adapter.opencode import OpenCodeAdapter

    raw = json.dumps({"channel": "harness-hil", "payload": {"name": "Question"}}).encode()
    evt = OpenCodeAdapter().parse_hook_line(raw)
    assert evt is not None
    assert evt.channel == "harness-hil"


# ---------------------------------------------------------------------------
# harness/adapter/opencode/hooks.py — branches
# ---------------------------------------------------------------------------


def test_hook_parser_returns_none_on_invalid_json(caplog):
    from harness.adapter.opencode.hooks import HookQuestionParser

    p = HookQuestionParser()
    with caplog.at_level(logging.WARNING):
        assert p.parse(b"{not json") is None


def test_hook_parser_returns_none_on_non_dict_json(caplog):
    from harness.adapter.opencode.hooks import HookQuestionParser

    p = HookQuestionParser()
    with caplog.at_level(logging.WARNING):
        assert p.parse(b'["list", "root"]') is None


def test_hook_parser_returns_none_when_channel_missing(caplog):
    from harness.adapter.opencode.hooks import HookQuestionParser

    p = HookQuestionParser()
    with caplog.at_level(logging.WARNING):
        assert p.parse(b'{"payload":{}}') is None
    assert any("channel" in rec.getMessage().lower() for rec in caplog.records)


def test_hook_parser_payload_non_dict_defaults_to_empty():
    from harness.adapter.opencode.hooks import HookQuestionParser

    p = HookQuestionParser()
    evt = p.parse(b'{"channel":"harness-hil","payload":"not-a-dict"}')
    assert evt is not None
    assert evt.payload == {}


def test_hook_parser_truncates_long_name_utf8_safe():
    from harness.adapter.opencode.hooks import HookQuestionParser

    long_name = "Q" * 500  # 500 bytes ASCII
    raw = json.dumps({"channel": "harness-hil", "payload": {"name": long_name}}).encode()
    evt = HookQuestionParser().parse(raw)
    assert evt is not None
    n = evt.payload["name"]
    assert n.endswith("…")
    assert len(n.encode("utf-8")) <= 256 + len("…".encode("utf-8"))


def test_hook_parser_truncate_cjk_boundary():
    """UTF-8 multibyte safety at boundary (Design §6 rationale Q5)."""
    from harness.adapter.opencode.hooks import HookQuestionParser

    # 汉 = 3 bytes each, 100 chars = 300 bytes
    long_cjk = "汉" * 100
    raw = json.dumps(
        {"channel": "harness-hil", "payload": {"name": long_cjk}}, ensure_ascii=False
    ).encode("utf-8")
    evt = HookQuestionParser().parse(raw)
    assert evt is not None
    n = evt.payload["name"]
    # UTF-8 decode must succeed → ends with ellipsis.
    assert n.endswith("…")


def test_hook_config_writer_writes_expected_structure(tmp_path):
    from harness.adapter.opencode.hooks import HookConfigWriter

    dest = tmp_path / ".opencode" / "hooks.json"
    HookConfigWriter().write(dest)
    body = json.loads(dest.read_text())
    assert body["version"] == 1
    assert any(item["match"]["name"] == "Question" for item in body["onToolCall"])


def test_mcp_degradation_push_toast_accumulates_messages():
    from harness.adapter.opencode.hooks import McpDegradation

    d = McpDegradation()
    assert d.toast_pushed is False
    assert d.messages == []
    d.push_toast("first")
    d.push_toast("second")
    assert d.toast_pushed is True
    assert d.messages == ["first", "second"]


def test_truncate_utf8_no_change_when_within_limit():
    """hooks.py `_truncate_utf8` short-circuit branch."""
    from harness.adapter.opencode.hooks import _truncate_utf8

    assert _truncate_utf8("abc") == "abc"


def test_extractor_truncate_no_change_when_within_limit():
    """extractor._truncate_utf8 short-circuit branch (lines 34-35)."""
    from harness.hil.extractor import _truncate_utf8

    assert _truncate_utf8("short") == "short"


# ---------------------------------------------------------------------------
# harness/pty/worker.py — guards / crashed / idempotent
# ---------------------------------------------------------------------------


class _FakePtyNoRead:
    """Minimal PtyProcessAdapter-shaped fake with no `read` attr → no reader thread."""

    def __init__(self):
        self.pid = 99
        self.started = False
        self.closed = False
        self.writes: list[bytes] = []

    def start(self):
        self.started = True

    def write(self, data: bytes):
        self.writes.append(data)
        return len(data)

    def close(self):
        self.closed = True


def test_worker_write_before_start_still_succeeds():
    """Cov: write path when _state == 'initialized' (not yet closed)."""
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    worker = PtyWorker(pty)
    # Before start, state is 'initialized' which is NOT in {"closed","closing"}.
    worker.write(b"hi")
    assert pty.writes == [b"hi"]


def test_worker_close_is_idempotent():
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    worker = PtyWorker(pty)
    worker.start()
    worker.close()
    # Re-invocation is a no-op per contract ("幂等（重复调用 no-op）").
    worker.close()
    assert pty.closed is True


def test_worker_write_after_close_raises_pty_closed_error():
    from harness.pty.errors import PtyClosedError
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    worker = PtyWorker(pty)
    worker.start()
    worker.close()
    with pytest.raises(PtyClosedError):
        worker.write(b"late")


def test_worker_start_idempotent_guard():
    """Line 57: start() second call is a no-op (state already 'running')."""
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    worker = PtyWorker(pty)
    worker.start()
    pty.started = False  # reset to detect a second call
    worker.start()  # must NOT re-invoke starter
    assert pty.started is False


def test_worker_state_transitions_visible():
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    worker = PtyWorker(pty)
    assert worker.state == "initialized"
    worker.start()
    assert worker.state == "running"
    worker.close()
    assert worker.state == "closed"


def test_worker_pid_property_mirrors_pty():
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    worker = PtyWorker(pty)
    assert worker.pid == 99


def test_worker_pid_property_handles_missing_attr():
    from harness.pty.worker import PtyWorker

    class NoPid:
        def start(self):
            pass

        def write(self, data):
            return len(data)

        def close(self):
            pass

    worker = PtyWorker(NoPid())
    assert worker.pid is None


@pytest.mark.asyncio
async def test_worker_start_creates_queue_when_loop_running():
    """Line 60 branch: byte_queue created under running loop."""
    from harness.pty.worker import PtyWorker

    pty = _FakePtyNoRead()
    loop = asyncio.get_event_loop()
    worker = PtyWorker(pty, loop=loop)
    worker.start()
    assert worker.byte_queue is not None
    worker.close()


# ---------------------------------------------------------------------------
# harness/hil/writeback.py — residual branches (no-op audit / no-op repo)
# ---------------------------------------------------------------------------


def test_writeback_success_with_audit_and_repo_none():
    """audit=None AND repo=None path must not raise (lines 103/115)."""
    from harness.domain.ticket import HilAnswer
    from harness.hil.writeback import HilWriteback

    class _W:
        def __init__(self):
            self.calls = []

        def write(self, data):
            self.calls.append(data)

    w = _W()
    wb = HilWriteback(worker=w, audit=None, ticket_repo=None, ticket_id="t1")
    ans = HilAnswer(
        question_id="q1",
        selected_labels=["yes"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    wb.write_answer(ans)
    assert len(w.calls) == 1


def test_writeback_pty_closed_with_repo_none_still_raises():
    """PtyClosedError path when repo is None (no transition call)."""
    from harness.domain.ticket import HilAnswer
    from harness.hil.writeback import HilWriteback
    from harness.pty.errors import PtyClosedError

    class _W:
        def write(self, data):
            raise PtyClosedError("EOF")

    wb = HilWriteback(worker=_W(), audit=None, ticket_repo=None, ticket_id="t1")
    ans = HilAnswer(
        question_id="q1",
        selected_labels=["late"],
        freeform_text=None,
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    with pytest.raises(PtyClosedError):
        wb.write_answer(ans)
    assert ans in wb.pending_answers


def test_writeback_freeform_with_whitespace_tabs_allowed():
    """Escape whitelist allows \\n \\t \\r (Design §6 rule (5))."""
    from harness.domain.ticket import HilAnswer
    from harness.hil.writeback import HilWriteback

    class _W:
        def __init__(self):
            self.calls = []

        def write(self, data):
            self.calls.append(data)

    w = _W()
    wb = HilWriteback(worker=w, audit=None, ticket_repo=None, ticket_id="t1")
    ans = HilAnswer(
        question_id="q1",
        selected_labels=[],
        freeform_text="line1\nline2\twithtab\rcr",
        answered_at=datetime.now(timezone.utc).isoformat(),
    )
    wb.write_answer(ans)
    assert len(w.calls) == 1


# ---------------------------------------------------------------------------
# harness/stream/banner_arbiter.py — residual branches
# ---------------------------------------------------------------------------


def test_banner_arbiter_running_verdict_when_neither_hil_nor_banner():
    from harness.stream.banner_arbiter import BannerConflictArbiter
    from harness.stream.events import StreamEvent

    events = [
        StreamEvent(kind="text", seq=1, payload={"text": "working"}),
        StreamEvent(kind="thinking", seq=2, payload={}),
    ]
    v = BannerConflictArbiter().arbitrate(events)
    assert v.verdict == "running"
    assert v.has_hil is False
    assert v.has_banner is False


def test_banner_arbiter_text_payload_non_string_ignored():
    """_is_terminate_banner line 67 — non-string text returns False."""
    from harness.stream.banner_arbiter import BannerConflictArbiter
    from harness.stream.events import StreamEvent

    events = [StreamEvent(kind="text", seq=1, payload={"text": 42})]
    v = BannerConflictArbiter().arbitrate(events)
    assert v.verdict == "running"


# ---------------------------------------------------------------------------
# harness/hil/control.py — all branches (single_select len-1, free_text fallback)
# ---------------------------------------------------------------------------


def test_control_deriver_empty_no_freeform_falls_back_to_free_text():
    from harness.hil.control import HilControlDeriver

    # Empty options, no freeform → free_text fallback (line 33).
    assert (
        HilControlDeriver().derive({"multi_select": False, "options": [], "allow_freeform": False})
        == "free_text"
    )


def test_control_deriver_single_option_without_freeform_is_single_select():
    from harness.hil.control import HilControlDeriver

    result = HilControlDeriver().derive(
        {"multi_select": False, "options": [{"label": "yes"}], "allow_freeform": False}
    )
    assert result == "single_select"
