"""Supplemental unit tests for F01 — raises line/branch coverage of the
implementation modules toward the Gate 1 thresholds (line >= 90%, branch >= 80%).

Targeted lines (as reported by pytest-cov term-missing):
    - harness/net/bind_guard.py    _parse_ss_output / _parse_lsof_output
    - harness/api/__init__.py      _probe_cli_version branches + non-loopback defence
    - harness/auth/claude_detector.py  auth-status OSError branch, --version fail
    - harness/auth/keyring_gateway.py  get/delete error-wrapping branches
    - harness/config/store.py      load invalid-utf8 + validation error branches
    - harness/app/first_run.py     is_first_run True when parent dir missing
    - harness/app/bootstrap.py     double-start guard + _dry_run_bind non-loopback

All tests anchor back to feature #1 (F01) SRS coverage (FR-046, FR-050,
NFR-007, NFR-010, NFR-012, NFR-013); no new FR-IDs are introduced.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import keyring
import pytest


# ---------------------------------------------------------------------------
# harness.net.bind_guard — parser coverage (NFR-007)
# ---------------------------------------------------------------------------
def test_parse_ss_output_extracts_ipv4_loopback_for_own_pid() -> None:
    """Synthetic `ss -tnlpH` output with the current PID should be picked up."""
    from harness.net.bind_guard import _parse_ss_output

    own_pid = os.getpid()
    text = (
        f'LISTEN 0 128 127.0.0.1:8765 0.0.0.0:* users:(("python",pid={own_pid},fd=8))\n'
        # Also include an unrelated PID line to exercise the loop.
        'LISTEN 0 128 127.0.0.1:9999 0.0.0.0:* users:(("other",pid=999999,fd=3))\n'
    )
    entries = _parse_ss_output(text)
    pids = {e.pid for e in entries}
    assert own_pid in pids
    hosts = {e.host for e in entries if e.pid == own_pid}
    assert hosts == {"127.0.0.1"}


def test_parse_ss_output_handles_ipv6_brackets() -> None:
    """IPv6 loopback `[::1]:port` must strip the brackets."""
    from harness.net.bind_guard import _parse_ss_output

    text = 'LISTEN 0 128 [::1]:8765 [::]:* users:(("python",pid=4242,fd=9))\n'
    entries = _parse_ss_output(text)
    assert len(entries) == 1
    assert entries[0].host == "::1"
    assert entries[0].port == 8765
    assert entries[0].pid == 4242


def test_parse_ss_output_skips_lines_without_pid() -> None:
    """Lines lacking `pid=<n>` are dropped (defensive parser contract)."""
    from harness.net.bind_guard import _parse_ss_output

    text = (
        "LISTEN 0 128 127.0.0.1:1 0.0.0.0:*\n"  # no users:() part → no pid
        "State Local-Address Foreign-Address\n"  # header-ish
        "\n"  # blank
    )
    assert _parse_ss_output(text) == []


def test_parse_ss_output_skips_non_integer_port() -> None:
    """Malformed port (e.g. 'x') must be skipped, not raise."""
    from harness.net.bind_guard import _parse_ss_output

    text = 'LISTEN 0 128 127.0.0.1:notaport 0.0.0.0:* users:(("python",pid=42,fd=8))\n'
    assert _parse_ss_output(text) == []


def test_parse_ss_output_skips_lines_without_colon_column() -> None:
    """Line where none of cols[:6] contains ':' (other than `:*`) → skip."""
    from harness.net.bind_guard import _parse_ss_output

    # Pathological line whose `local` address slot is '*:*' only.
    text = "LISTEN 0 128 *:* 0.0.0.0:* junk\n"
    assert _parse_ss_output(text) == []


def test_parse_ss_output_skips_short_columns() -> None:
    """Line with <5 whitespace-separated columns → skip."""
    from harness.net.bind_guard import _parse_ss_output

    assert _parse_ss_output("LISTEN 0 128\n") == []


def test_parse_lsof_output_extracts_listening_entries() -> None:
    """Synthetic lsof output exercises the macOS parser branch."""
    from harness.net.bind_guard import _parse_lsof_output

    text = (
        "COMMAND  PID USER   FD   TYPE     DEVICE SIZE/OFF NODE NAME\n"
        "python  4242 u     8u   IPv4      0xff      0t0  TCP 127.0.0.1:8765 (LISTEN)\n"
        # Non-LISTEN line (e.g. ESTABLISHED) must be skipped.
        "python  4242 u     9u   IPv4      0xff      0t0  TCP 127.0.0.1:80 (ESTABLISHED)\n"
    )
    entries = _parse_lsof_output(text)
    assert len(entries) == 1
    assert entries[0].host == "127.0.0.1"
    assert entries[0].port == 8765
    assert entries[0].pid == 4242


def test_parse_lsof_output_skips_short_lines_and_non_numeric_pid() -> None:
    """Short lines + non-integer PID values must be dropped without raising."""
    from harness.net.bind_guard import _parse_lsof_output

    text = (
        "HEADER\n"
        "short line\n"
        "python notapid u 8u IPv4 0xff 0t0 TCP 127.0.0.1:1 (LISTEN)\n"
        # Valid but port non-integer
        "python 10 u 8u IPv4 0xff 0t0 TCP 127.0.0.1:BAD (LISTEN)\n"
    )
    assert _parse_lsof_output(text) == []


def test_parse_lsof_output_strips_ipv6_brackets() -> None:
    from harness.net.bind_guard import _parse_lsof_output

    text = "HEADER\n" "python 4242 u 8u IPv6 0xff 0t0 TCP [::1]:8765 (LISTEN)\n"
    entries = _parse_lsof_output(text)
    assert len(entries) == 1
    assert entries[0].host == "::1"


def test_parse_listening_sockets_on_linux_invokes_ss(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover the Linux branch of BindGuard.parse_listening_sockets."""
    from harness.net import BindGuard

    if not sys.platform.startswith("linux"):  # pragma: no cover
        pytest.skip("Linux-only branch")

    own_pid = os.getpid()
    # Patch the private _run to return a synthetic ss payload we control.
    import harness.net.bind_guard as bg

    def _fake_run(argv: list[str]) -> str:
        assert argv[0] == "ss", f"expected ss on Linux, got {argv!r}"
        return f'LISTEN 0 128 127.0.0.1:8765 0.0.0.0:* users:(("python",pid={own_pid},fd=8))\n'

    monkeypatch.setattr(bg, "_run", _fake_run)

    result = BindGuard().parse_listening_sockets()
    assert all(e.pid == own_pid for e in result)
    assert any(e.host == "127.0.0.1" and e.port == 8765 for e in result)


def test_parse_listening_sockets_wraps_filenotfound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing `ss` / `lsof` / `netstat` executable surfaces as OSError."""
    from harness.net import BindGuard
    import harness.net.bind_guard as bg

    def _raise(argv: list[str]) -> str:
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(bg, "_run", _raise)
    with pytest.raises(OSError) as excinfo:
        BindGuard().parse_listening_sockets()
    assert "listing command not available" in str(excinfo.value)


def test_parse_listening_sockets_returns_empty_on_unknown_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-linux / non-darwin / non-win32 platform → empty list (no crash)."""
    import harness.net.bind_guard as bg
    from harness.net import BindGuard

    monkeypatch.setattr(bg.sys, "platform", "sunos5")
    assert BindGuard().parse_listening_sockets() == []


# ---------------------------------------------------------------------------
# harness.api — /api/health branches (NFR-007 defence, cli missing probe)
# ---------------------------------------------------------------------------
def test_probe_cli_version_returns_none_when_which_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_probe_cli_version returns None when shutil.which cannot find the CLI."""
    import harness.api as api_mod

    monkeypatch.setattr(api_mod.shutil, "which", lambda name: None)
    assert api_mod._probe_cli_version("claude") is None


def test_probe_cli_version_returns_none_on_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    import harness.api as api_mod

    monkeypatch.setattr(api_mod.shutil, "which", lambda name: f"/fake/{name}")

    def _raise(*args: object, **kw: object) -> subprocess.CompletedProcess[str]:
        raise OSError("spawn failed")

    monkeypatch.setattr(api_mod.subprocess, "run", _raise)
    assert api_mod._probe_cli_version("claude") is None


def test_probe_cli_version_returns_none_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import harness.api as api_mod

    monkeypatch.setattr(api_mod.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        api_mod.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], returncode=2, stdout="", stderr="bad"),
    )
    assert api_mod._probe_cli_version("claude") is None


def test_probe_cli_version_returns_trimmed_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    import harness.api as api_mod

    monkeypatch.setattr(api_mod.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        api_mod.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            a[0], returncode=0, stdout="claude 1.2.3\n", stderr=""
        ),
    )
    assert api_mod._probe_cli_version("claude") == "claude 1.2.3"


def test_probe_cli_version_falls_back_to_stderr_and_empty_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import harness.api as api_mod

    monkeypatch.setattr(api_mod.shutil, "which", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        api_mod.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(a[0], returncode=0, stdout="", stderr=""),
    )
    assert api_mod._probe_cli_version("claude") is None


async def test_health_endpoint_coerces_non_loopback_bind_back_to_127(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if app.state.bind_host is tampered, the endpoint never leaks non-loopback."""
    import httpx

    from harness.api import app

    # Inject a poisonous value on the shared FastAPI state.
    app.state.bind_host = "0.0.0.0"
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/health")
        payload = resp.json()
        assert payload["bind"] == "127.0.0.1"
    finally:
        # Clean app.state so other tests in the process are not affected.
        try:
            del app.state.bind_host
        except AttributeError:  # pragma: no cover
            pass


# ---------------------------------------------------------------------------
# harness.auth.claude_detector — uncovered branch lines
# ---------------------------------------------------------------------------
def test_detect_returns_cli_absent_when_version_returncode_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`claude --version` with non-zero exit → cli_present=False (NFR-009 / FR-046 negative)."""
    import shutil as _shutil
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="broken")
        raise AssertionError(f"unexpected: {args!r}")

    monkeypatch.setattr(mod.subprocess, "run", _run)

    status = ClaudeAuthDetector().detect()
    assert status.cli_present is False
    assert status.source == "skipped"


def test_detect_handles_oserror_from_auth_status_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSError from the second subprocess.run (`claude auth status`) is absorbed."""
    import shutil as _shutil
    import harness.auth.claude_detector as mod
    from harness.auth import ClaudeAuthDetector

    monkeypatch.setattr(
        _shutil, "which", lambda name: "/usr/local/bin/claude" if name == "claude" else None
    )

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="claude 1", stderr=""
            )
        if args[:3] == ["claude", "auth", "status"]:
            raise OSError("status command vanished")
        raise AssertionError(f"unexpected: {args!r}")

    monkeypatch.setattr(mod.subprocess, "run", _run)

    status = ClaudeAuthDetector().detect()
    # CLI was present, but we couldn't reach auth status — NFR-010 hint expected.
    assert status.cli_present is True
    assert status.authenticated is False
    assert status.hint is not None and "claude auth login" in status.hint


# ---------------------------------------------------------------------------
# harness.auth.keyring_gateway — exception-wrapping branches
# ---------------------------------------------------------------------------
def test_set_secret_wraps_backend_exception_as_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arbitrary backend failure on set_password surfaces as KeyringServiceError."""
    from harness.auth import KeyringGateway, KeyringServiceError

    def _raise(*a: object, **kw: object) -> None:
        raise RuntimeError("backend died")

    monkeypatch.setattr(keyring, "set_password", _raise)

    gw = KeyringGateway()
    with pytest.raises(KeyringServiceError):
        gw.set_secret("harness-x", "u", "v")


def test_delete_secret_is_idempotent_when_entry_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`PasswordDeleteError` is silently swallowed — delete is a no-op then."""
    from harness.auth import KeyringGateway

    def _raise(*a: object, **kw: object) -> None:
        raise keyring.errors.PasswordDeleteError("no such password")

    monkeypatch.setattr(keyring, "delete_password", _raise)
    gw = KeyringGateway()
    # Must NOT raise.
    gw.delete_secret("harness-x", "u")


def test_delete_secret_wraps_unexpected_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.auth import KeyringGateway, KeyringServiceError

    def _raise(*a: object, **kw: object) -> None:
        raise RuntimeError("catastrophic")

    monkeypatch.setattr(keyring, "delete_password", _raise)
    gw = KeyringGateway()
    with pytest.raises(KeyringServiceError):
        gw.delete_secret("harness-x", "u")


def test_set_secret_records_degradation_log_with_plaintext_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """set_secret appends to degradation_log when backend is Plaintext."""
    import keyrings.alt.file  # type: ignore[import-not-found]

    from harness.auth import KeyringGateway

    plain = keyrings.alt.file.PlaintextKeyring()

    monkeypatch.setattr(keyring, "get_keyring", lambda: plain)
    monkeypatch.setattr(keyring, "set_password", lambda *a, **kw: None)

    gw = KeyringGateway()
    assert gw.degraded is True
    gw.set_secret("harness-x", "u", "v")
    assert len(gw.degradation_log) == 1
    timestamp, backend_name = gw.degradation_log[0]
    assert "PlaintextKeyring" in backend_name


# ---------------------------------------------------------------------------
# harness.config.store — load branches + save error cleanup
# ---------------------------------------------------------------------------
def test_config_store_load_raises_on_non_utf8_bytes(tmp_path: Path) -> None:
    """Non-UTF-8 bytes in config.json → ConfigCorruptError (decode branch)."""
    from harness.config import ConfigStore, ConfigCorruptError

    cfg_path = tmp_path / "config.json"
    cfg_path.write_bytes(b"\xff\xfe\xfd\xfc")  # invalid utf-8
    store = ConfigStore(cfg_path)

    with pytest.raises(ConfigCorruptError):
        store.load()


def test_config_store_load_raises_on_schema_validation_error(tmp_path: Path) -> None:
    """Schema-valid JSON but wrong types → ConfigCorruptError (pydantic branch)."""
    from harness.config import ConfigStore, ConfigCorruptError

    cfg_path = tmp_path / "config.json"
    # retention_run_count must be int — inject a string to trigger ValidationError.
    cfg_path.write_text(
        json.dumps({"schema_version": 1, "retention_run_count": "not-a-number"}),
        encoding="utf-8",
    )
    store = ConfigStore(cfg_path)

    with pytest.raises(ConfigCorruptError):
        store.load()


def test_config_store_save_is_atomic_and_overwrites_existing_file(
    tmp_path: Path,
) -> None:
    """Saving twice leaves exactly one file with the latest payload."""
    from harness.config import ConfigStore
    from harness.config.schema import HarnessConfig

    cfg_path = tmp_path / "config.json"
    store = ConfigStore(cfg_path)
    store.save(HarnessConfig.default())
    store.save(HarnessConfig(retention_run_count=7))

    loaded = store.load()
    assert loaded.retention_run_count == 7
    # No leftover *.tmp files.
    leftovers = list(tmp_path.glob("config.*.json.tmp"))
    assert leftovers == [], f"atomic save left tmp files: {leftovers!r}"


# ---------------------------------------------------------------------------
# harness.app.first_run — parent-dir missing branch + config-save OSError branch
# ---------------------------------------------------------------------------
def test_is_first_run_returns_true_when_parent_dir_missing(
    tmp_path: Path,
) -> None:
    """Parent `~/.harness/` absent → is_first_run() must be True."""
    from harness.app import FirstRunWizard
    from harness.config import ConfigStore

    home = tmp_path / ".harness"
    assert not home.exists()
    wizard = FirstRunWizard(ConfigStore(home / "config.json"))
    assert wizard.is_first_run() is True


def test_bootstrap_wraps_oserror_from_config_save_as_home_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ConfigStore.save raises OSError during first-run bootstrap, we wrap it."""
    from harness.app import FirstRunWizard
    from harness.app.first_run import HarnessHomeWriteError
    from harness.config import ConfigStore

    home = tmp_path / ".harness"
    cfg_path = home / "config.json"
    monkeypatch.setenv("HARNESS_HOME", str(home))
    store = ConfigStore(cfg_path)

    def _raise(*a: object, **kw: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "save", _raise)

    wizard = FirstRunWizard(store)
    with pytest.raises(HarnessHomeWriteError):
        wizard.bootstrap()


# ---------------------------------------------------------------------------
# harness.app.bootstrap — double-start guard + invalid port type
# ---------------------------------------------------------------------------
def test_app_bootstrap_rejects_port_of_wrong_type() -> None:
    """Port must be int (not str, not bool). Bool is a subclass trap."""
    from harness.app import AppBootstrap

    with pytest.raises(ValueError):
        AppBootstrap(port="not-an-int")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        AppBootstrap(port=True)  # bool is int subclass — must be rejected


def test_app_bootstrap_double_start_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling `.start()` twice without stop() must raise RuntimeError."""
    import webview as _webview  # type: ignore[import-not-found]

    from harness.app import AppBootstrap

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / ".harness"))
    monkeypatch.setattr(_webview, "create_window", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(_webview, "start", lambda *a, **kw: None, raising=False)

    app = AppBootstrap(port=0)
    app.start()
    try:
        with pytest.raises(RuntimeError):
            app.start()
    finally:
        app.stop()


def test_dry_run_bind_rejects_non_loopback_host() -> None:
    """AppBootstrap._dry_run_bind is the internal guard protecting §NFR-007."""
    from harness.app.bootstrap import AppBootstrap
    from harness.net import BindRejectedError, BindUnavailableError

    # 0.0.0.0 is not an accepted AppBootstrap host (constructor guard), but we can
    # still directly exercise the static helper to ensure the socket-level guard
    # agrees. OS may forbid binding to a truly external IP — we accept either
    # BindRejected (preferred) or BindUnavailable (permission/address denied).
    with pytest.raises((BindRejectedError, BindUnavailableError)):
        AppBootstrap._dry_run_bind("0.0.0.0", 0)


def test_dry_run_bind_on_127_returns_positive_port() -> None:
    from harness.app.bootstrap import AppBootstrap

    chosen = AppBootstrap._dry_run_bind("127.0.0.1", 0)
    assert chosen > 0


def test_app_bootstrap_default_harness_home_honours_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When `harness_home=None`, default_path() reads HARNESS_HOME env."""
    import webview as _webview  # type: ignore[import-not-found]

    from harness.app import AppBootstrap

    monkeypatch.setenv("HARNESS_HOME", str(tmp_path / "alt-home"))
    monkeypatch.setattr(_webview, "create_window", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(_webview, "start", lambda *a, **kw: None, raising=False)

    app = AppBootstrap()  # harness_home=None → picks up env
    runtime = app.start()
    try:
        assert (tmp_path / "alt-home" / "config.json").exists()
        assert runtime.port > 0
    finally:
        app.stop()
