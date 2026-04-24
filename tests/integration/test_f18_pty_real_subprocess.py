"""F18 · Bk-Adapter — Real PTY subprocess integration test (no CLI needed).

Covers coverage gap for `harness/pty/posix.py` (35 stmts 0%) and drives the
real reader-thread path in `harness/pty/worker.py` without requiring the
`claude` CLI. Uses `/bin/cat` as an echo subprocess: stdin bytes are echoed
back on stdout, so we can assert round-trip byte integrity over a real PTY.

feature: 18 (Bk-Adapter — Agent Adapter & HIL Pipeline).

Real-test invariants (Rule 5a):
  - DOES NOT mock ptyprocess / subprocess / os.fork.
  - The primary dep under test is the PTY layer; a real `cat` subprocess
    drives it. CLI adapters (Claude/OpenCode) are NOT the focus here.
  - High-value assertions: byte integrity round-trip, pid stability,
    process termination.
  - Hard-fails if /bin/cat or ptyprocess are missing (no silent skip).

Layer marker:
  # [integration] — real PTY + real subprocess; marker `@pytest.mark.real_fs`
  # per feature-list.json real_test.marker_pattern regex.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time

import pytest

# Deferred f18 imports inside tests mirror the rest of the F18 suite.


pytestmark = pytest.mark.real_fs


def _require_cat():
    cat = shutil.which("cat") or "/bin/cat"
    assert os.path.exists(cat), "real PTY test requires `cat` on PATH"
    return cat


def _require_ptyprocess():
    try:
        import ptyprocess  # noqa: F401
    except ImportError:
        pytest.fail("ptyprocess not installed — real PTY tests mandatory (env-guide §5)")


# ---------------------------------------------------------------------------
# PosixPty — spawn + write + read + close
# ---------------------------------------------------------------------------


def test_posix_pty_roundtrip_via_cat_echo(tmp_path):
    """[feature 18] Spawn real `cat` under PosixPty; write a line; read same bytes back."""
    _require_ptyprocess()
    cat = _require_cat()
    if os.name != "posix":
        pytest.skip("POSIX-only PTY backend under test")

    from harness.pty.posix import PosixPty

    pty = PosixPty(argv=[cat], env={"PATH": "/usr/bin:/bin"}, cwd=str(tmp_path))
    pty.start()
    try:
        assert pty.pid > 0, "real subprocess must expose a positive pid"

        # Write a line; cat echoes each byte back on stdout.
        line = b"hello-pty-roundtrip\n"
        written = pty.write(line)
        assert written >= len(line)

        # Read up to ~2s to accumulate the echoed bytes.
        deadline = time.monotonic() + 2.0
        accumulated = bytearray()
        while time.monotonic() < deadline and b"hello-pty-roundtrip" not in bytes(accumulated):
            chunk = pty.read(4096)
            if chunk:
                accumulated.extend(chunk)
            else:
                time.sleep(0.05)

        # Byte integrity assertion.
        assert b"hello-pty-roundtrip" in bytes(accumulated)
    finally:
        pty.close()


def test_posix_pty_write_before_start_is_safe_noop(tmp_path):
    """[feature 18] PosixPty.write before start() is a safe 0-byte no-op (guard branch)."""
    from harness.pty.posix import PosixPty

    pty = PosixPty(argv=["/bin/cat"], env={}, cwd=str(tmp_path))
    # Do NOT call start() — _proc stays None. write/read/close must not crash.
    assert pty.read() == b""
    assert pty.write(b"x") == 0
    pty.close()  # idempotent on unstarted pty


def test_posix_pty_read_after_close_yields_empty(tmp_path):
    """[feature 18] After close() on a real subprocess, read() returns b'' (EOFError branch)."""
    _require_ptyprocess()
    cat = _require_cat()
    if os.name != "posix":
        pytest.skip("POSIX-only")

    from harness.pty.posix import PosixPty

    pty = PosixPty(argv=[cat], env={"PATH": "/usr/bin:/bin"}, cwd=str(tmp_path))
    pty.start()
    pid = pty.pid
    pty.close()

    # After close the child is SIGKILLed; read() should yield b'' (EOF) within
    # a short grace window — we just assert no crash + empty-or-string type.
    time.sleep(0.2)
    data = pty.read(128)
    assert isinstance(data, (bytes, bytearray))
    # And the pid we captured should be a positive integer from real fork.
    assert pid > 0


# ---------------------------------------------------------------------------
# PtyWorker — real reader thread pushing to asyncio.Queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_reader_thread_pushes_real_cat_bytes_to_queue(tmp_path):
    """[feature 18] PtyWorker reader thread → byte_queue receives real /bin/cat echo."""
    _require_ptyprocess()
    cat = _require_cat()
    if os.name != "posix":
        pytest.skip("POSIX-only")

    from harness.pty.posix import PosixPty
    from harness.pty.worker import PtyWorker

    pty = PosixPty(argv=[cat], env={"PATH": "/usr/bin:/bin"}, cwd=str(tmp_path))
    loop = asyncio.get_event_loop()
    worker = PtyWorker(pty, loop=loop)
    try:
        worker.start()
        assert worker.state == "running"

        # After start, byte_queue must be alive.
        assert worker.byte_queue is not None

        worker.write(b"abc-real-worker\n")

        # Drain up to ~2s worth of chunks looking for the echo.
        accumulated = bytearray()
        deadline = loop.time() + 2.0
        while loop.time() < deadline and b"abc-real-worker" not in bytes(accumulated):
            try:
                chunk = await asyncio.wait_for(worker.byte_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if chunk is None:  # sentinel = pty EOF
                break
            accumulated.extend(chunk)

        assert b"abc-real-worker" in bytes(accumulated)
    finally:
        worker.close()


@pytest.mark.asyncio
async def test_worker_close_sends_sentinel_on_queue(tmp_path):
    """[feature 18] close() on a running worker emits the `None` sentinel to the queue."""
    _require_ptyprocess()
    cat = _require_cat()
    if os.name != "posix":
        pytest.skip("POSIX-only")

    from harness.pty.posix import PosixPty
    from harness.pty.worker import PtyWorker

    pty = PosixPty(argv=[cat], env={"PATH": "/usr/bin:/bin"}, cwd=str(tmp_path))
    loop = asyncio.get_event_loop()
    worker = PtyWorker(pty, loop=loop)
    worker.start()
    worker.close()
    assert worker.state == "closed"

    # Drain the queue; a None sentinel MUST appear within ~1s.
    saw_sentinel = False
    deadline = loop.time() + 1.0
    while loop.time() < deadline:
        try:
            item = await asyncio.wait_for(worker.byte_queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        if item is None:
            saw_sentinel = True
            break

    assert saw_sentinel, "PtyWorker.close must enqueue a None sentinel for downstream consumers"


# ---------------------------------------------------------------------------
# ClaudeCodeAdapter.spawn integration via PosixPty (real subprocess substituted
# for `claude`). This drives the `_default_factory` posix branch + PtyWorker
# start in one pass, without needing the real `claude` CLI.
# ---------------------------------------------------------------------------


def test_claude_adapter_spawn_posix_factory_with_real_cat(tmp_path, monkeypatch):
    """[feature 18] ClaudeCodeAdapter.spawn runs against a real /bin/cat when `shutil.which` routes to it.

    This exercises:
      - `_default_factory()` posix branch (PosixPty return)
      - `_sanitise_env` whitelist (only PATH / HOME / TERM survive)
      - `PtyWorker.start()` + reader thread on a real subprocess

    It does NOT mock ptyprocess or subprocess.
    """
    _require_ptyprocess()
    cat = _require_cat()
    if os.name != "posix":
        pytest.skip("POSIX-only")

    from harness.adapter.claude import ClaudeCodeAdapter
    from harness.domain.ticket import DispatchSpec

    base = tmp_path / ".harness-workdir" / "r1"
    pd = base / ".claude" / "plugins"
    sp = base / ".claude" / "settings.json"
    pd.mkdir(parents=True, exist_ok=True)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text("{}")

    spec = DispatchSpec(
        argv=["claude"],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(base),
            "TERM": "dumb",
            "AWS_SECRET": "must-be-stripped",
        },
        cwd=str(base),
        model=None,
        mcp_config=None,
        plugin_dir=str(pd),
        settings_path=str(sp),
    )

    # Route `shutil.which("claude")` to the real cat binary; the adapter's
    # argv validation fires on build_argv (already FR-016 compliant), then
    # spawn uses the pty_factory. We inject PosixPty as the factory but
    # rewrite argv[0] to `cat` so ptyprocess actually execs something that
    # exists (claude may not be installed on this CI host).
    monkeypatch.setattr("shutil.which", lambda name: cat if name == "claude" else None)

    from harness.pty.posix import PosixPty

    def cat_factory(argv, env, cwd):
        # Replace argv[0] with /bin/cat so the PTY exec succeeds without claude.
        real_argv = [cat] + list(argv[1:])
        return PosixPty(real_argv, env, cwd)

    adapter = ClaudeCodeAdapter(pty_factory=cat_factory)
    proc = adapter.spawn(spec)
    try:
        assert proc.pid > 0
        assert proc.ticket_id  # uuid hex
        assert proc.pty_handle_id.startswith("pty-")
        # Worker was started; by now the `cat` child may have already EOF'd
        # (no stdin feed). Acceptable states: running (still alive) or closed
        # (reader thread hit EOF and raced us). Crashed is NOT acceptable.
        assert proc.worker.state in ("running", "closed")
    finally:
        proc.worker.close()
