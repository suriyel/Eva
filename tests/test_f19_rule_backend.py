"""F19 · Bk-Dispatch — RuleBackend rule-chain tests.

Covers Test Inventory: T09, T10, T11, T12, T13, T14, T15.
SRS: FR-022 AC-1/AC-2 · §IC RuleBackend.decide · §IS flow TD branches:
  Banner · RateLimit · Perm · ExitOk · SkillErr.

Layer marker:
  # [unit] — pure function; no I/O. No real-test exemption needed here
  # because classifier real-http integration is in tests/integration/test_f19_real_http.py.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# T09 — FUNC/happy — Traces To: FR-022 AC-1 · §IS flow branch ExitOk
# Kills: healthy ticket mis-classified as ABORT.
# ---------------------------------------------------------------------------
def test_t09_rule_backend_exit_zero_no_banner_empty_stderr_returns_completed():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    req = ClassifyRequest(
        exit_code=0,
        stderr_tail="",
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    assert verdict.verdict == "COMPLETED"
    assert verdict.anomaly is None
    assert verdict.backend == "rule"


# ---------------------------------------------------------------------------
# T10 — FUNC/happy — Traces To: FR-022 AC-2 · §IS flow branch Banner
# Kills: context_overflow regex miss (e.g. case-sensitive).
# ---------------------------------------------------------------------------
def test_t10_rule_backend_context_window_stderr_returns_retry_context_overflow():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    req = ClassifyRequest(
        exit_code=1,
        stderr_tail="... context window exceeded by 3k tokens ...",
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    assert verdict.verdict == "RETRY"
    assert verdict.anomaly == "context_overflow"
    assert verdict.backend == "rule"


# ---------------------------------------------------------------------------
# T11 — FUNC/error — Traces To: §IS flow branch RateLimit
# Kills: rate_limit / HTTP 429 missed.
# ---------------------------------------------------------------------------
def test_t11_rule_backend_rate_limit_stderr_returns_retry_rate_limit():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    req = ClassifyRequest(
        exit_code=1,
        stderr_tail="HTTP 429 rate limit on API key",
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    assert verdict.verdict == "RETRY"
    assert verdict.anomaly == "rate_limit"
    assert verdict.backend == "rule"


# ---------------------------------------------------------------------------
# T12 — FUNC/error — Traces To: §IS flow branch Perm
# Kills: permission denied erroneously retried (infinite loop).
# ---------------------------------------------------------------------------
def test_t12_rule_backend_permission_denied_returns_abort_no_retry():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    req = ClassifyRequest(
        exit_code=13,
        stderr_tail="chmod: cannot access '/etc/shadow': Permission denied",
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    assert verdict.verdict == "ABORT"
    assert verdict.backend == "rule"
    # Must NOT be classified as retry — permission errors are fatal.
    assert verdict.verdict != "RETRY"


# ---------------------------------------------------------------------------
# T13 — FUNC/error — Traces To: §IS flow branch SkillErr
# Kills: unknown failure dropped / classified COMPLETED.
# ---------------------------------------------------------------------------
def test_t13_rule_backend_unknown_failure_returns_abort_skill_error():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    req = ClassifyRequest(
        exit_code=2,
        stderr_tail="segfault at 0xdeadbeef",
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    assert verdict.verdict == "ABORT"
    assert verdict.anomaly == "skill_error"
    assert verdict.backend == "rule"


# ---------------------------------------------------------------------------
# T14 — BNDRY/edge — Traces To: §BC exit_code=None
# Kills: None coerced to 0 → false COMPLETED.
# ---------------------------------------------------------------------------
def test_t14_rule_backend_exit_code_none_is_not_completed():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    req = ClassifyRequest(
        exit_code=None,
        stderr_tail="",
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    # Strong negative — whatever the concrete verdict is, it MUST NOT be COMPLETED.
    assert (
        verdict.verdict != "COMPLETED"
    ), "exit_code=None means the process status is unknown; must not yield COMPLETED"
    # Per design — should fall into skill_error branch (ABORT).
    assert verdict.verdict == "ABORT"
    assert verdict.anomaly == "skill_error"


# ---------------------------------------------------------------------------
# T15 — BNDRY/edge — Traces To: §BC stderr_tail 32 KB truncation
# Kills: head-side truncation (losing the trailing "context window" marker).
# ---------------------------------------------------------------------------
def test_t15_rule_backend_tail_truncation_preserves_trailing_context_window_marker():
    from harness.dispatch.classifier.models import ClassifyRequest
    from harness.dispatch.classifier.rule_backend import RuleBackend

    # 100 KB of benign filler, then the real marker at the tail.
    filler = "A" * (100 * 1024)
    trailing = " ... context window exceeded ..."
    req = ClassifyRequest(
        exit_code=1,
        stderr_tail=filler + trailing,  # 100 KB + marker
        stdout_tail="",
        has_termination_banner=False,
    )
    verdict = RuleBackend().decide(req)

    # If implementation truncates from the HEAD it preserves the marker — good.
    # If it truncates from the TAIL (classic bug), it loses the marker and falls
    # into skill_error. That failure is what this test kills.
    assert (
        verdict.verdict == "RETRY"
    ), "tail-preserving truncation must retain the context_overflow marker"
    assert verdict.anomaly == "context_overflow"
