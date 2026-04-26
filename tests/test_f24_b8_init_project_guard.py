"""Feature #24 B8 — `scripts/init_project.py` argparse-flag prefix guard.

Traces To
=========
  B8-P1  §IC `_validate_safe_arg` happy path                         (FUNC/happy)
  B8-N1  §IC guard / B8 direct hit — argv = ['--version']            (SEC/cli-injection)
  B8-N2  §IC guard — `-x` rejected                                   (SEC/cli-injection)
  B8-N3  §IC guard — `--path --help` rejected                        (SEC/cli-injection)
  B8-N4  §Boundary `args.path` — `./ok-name` accepted                (BNDRY/edge)
  §Implementation Summary B8 (init_project.py guard + reserved flags set)

Rule 4 wrong-impl challenge:
  - 「守卫漏掉单 `-` 前缀」                          → B8-N2 FAIL
  - 「守卫只检查 project_name 不检查 --path」        → B8-N3 FAIL
  - 「守卫拒绝所有含 `-` 字符」(误伤 my-proj)         → B8-P1 FAIL
  - 「守卫拒绝 `./ok-name` (正常相对路径)」          → B8-N4 FAIL

Rule 5 layer:
  [unit] runs the script via `subprocess` against `scripts/init_project.py` —
  exercises argparse boundary deterministically. Real fs assertion (residual
  dirs absent) lives in tests/integration/test_f24_real_repo_residual_dirs.py
  with @pytest.mark.real_fs.

Feature ref: feature 24

[unit] — uses subprocess + tmp_path; no mock on argparse / sys.exit.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "init_project.py"


def _run(argv: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _has_validate_safe_arg() -> bool:
    """Detect whether the fix has been applied — `_validate_safe_arg` exists."""
    text = SCRIPT.read_text(encoding="utf-8")
    return "_validate_safe_arg" in text


def _has_reserved_flags_set() -> bool:
    """Detect whether `_RESERVED_FLAGS` has been declared per Implementation Summary B8."""
    text = SCRIPT.read_text(encoding="utf-8")
    return "_RESERVED_FLAGS" in text


# ------------------------------------------------------------------ B8-P1 ----
def test_b8_p1_happy_proj_name_with_internal_dash(tmp_path: pathlib.Path) -> None:
    """Legitimate `my-proj` must be accepted (dash not at index 0).

    Combined with fix-presence check: `_validate_safe_arg` and `_RESERVED_FLAGS`
    must exist in the script (per §IS B8). In Red phase neither exists, so
    this test fails on the structural assertion before exercising the happy
    flow.
    """
    assert (
        _has_validate_safe_arg()
    ), "scripts/init_project.py: `_validate_safe_arg` not defined — fix not applied"
    assert (
        _has_reserved_flags_set()
    ), "scripts/init_project.py: `_RESERVED_FLAGS` not declared — fix not applied"

    proc = _run(["my-proj"], cwd=tmp_path)
    assert proc.returncode == 0, (
        f"legit project name rejected: rc={proc.returncode} " f"stderr={proc.stderr!r}"
    )
    fl = tmp_path / "feature-list.json"
    assert fl.is_file(), f"feature-list.json not created at {fl}"
    content = fl.read_text(encoding="utf-8")
    assert "my-proj" in content, f"project_name not persisted in {fl}"


# ------------------------------------------------------------------ B8-N1 ----
def test_b8_n1_reject_argparse_flag_as_project_name(tmp_path: pathlib.Path) -> None:
    """argv = ['--version'] must exit non-zero AND not create directory."""
    # Sanity: the cwd is empty before.
    proc = _run(["--version"], cwd=tmp_path)
    # Must reject (currently argparse may print --version banner OR treat as
    # missing required arg; ANY exit code != 0 + no `--version/` dir is OK
    # PROVIDED stderr explains).
    assert proc.returncode != 0, (
        f"--version was accepted as project_name; rc={proc.returncode} " f"stdout={proc.stdout!r}"
    )
    # Must not have created a literal '--version' directory or feature-list.json.
    bad_dir = tmp_path / "--version"
    assert not bad_dir.exists(), f"created directory '{bad_dir}' from argparse flag — guard missing"
    # stderr must mention either `argparse flag` (custom guard) or
    # `unrecognized arguments` / `required` (argparse default refusal).
    stderr_low = (proc.stderr or "").lower()
    expected_markers = ("argparse flag", "reserved", "looks like", "refuse")
    assert any(
        m in stderr_low for m in expected_markers
    ), f"stderr lacks explicit guard message; got {proc.stderr!r}"


# ------------------------------------------------------------------ B8-N2 ----
def test_b8_n2_reject_dash_prefix_token(tmp_path: pathlib.Path) -> None:
    """argv = ['-x'] must be rejected; no `-x/` directory written."""
    proc = _run(["-x"], cwd=tmp_path)
    assert proc.returncode != 0, f"'-x' accepted as project_name; rc={proc.returncode}"
    assert not (tmp_path / "-x").exists(), "rogue '-x' directory created"
    # Specific guard message expected:
    stderr_low = (proc.stderr or "").lower()
    assert (
        "looks like" in stderr_low or "argparse flag" in stderr_low
    ), f"explicit prefix guard missing; stderr={proc.stderr!r}"


# ------------------------------------------------------------------ B8-N3 ----
def test_b8_n3_reject_path_value_as_argparse_flag(tmp_path: pathlib.Path) -> None:
    """argv = ['p', '--path', '--help'] must reject `--help` as path value.

    Combined with fix-presence: explicit guard message must mention --path
    (the FIXED behaviour). Bare argparse `usage:` print is insufficient
    because it lacks targeted diagnostic — Rule 4 wrong-impl: "exit non-zero
    on any error" doesn't capture the SEC value.
    """
    assert (
        _has_validate_safe_arg()
    ), "scripts/init_project.py: `_validate_safe_arg` not defined — fix not applied"

    proc = _run(["p", "--path", "--help"], cwd=tmp_path)
    assert proc.returncode != 0, f"--path=--help slipped through; rc={proc.returncode}"
    assert not (tmp_path / "--help").exists(), "rogue '--help' directory created"
    stderr_low = (proc.stderr or "").lower()
    # After fix: stderr MUST contain explicit guard wording referencing --path
    # or "reserved" / "argparse flag" — bare argparse "usage:" is no longer
    # acceptable.
    assert (
        "--path" in stderr_low or "reserved" in stderr_low or "argparse flag" in stderr_low
    ), f"explicit guard message missing; stderr={proc.stderr!r}"


# ------------------------------------------------------------------ B8-N4 ----
def test_b8_n4_legit_path_with_internal_dash_accepted(
    tmp_path: pathlib.Path,
) -> None:
    """argv = ['p', '--path', './ok-name'] must succeed (BNDRY edge).

    Combined with fix-presence: the fixed guard MUST allow internal-dash names.
    This is a Rule 4 wrong-impl trap: a too-greedy guard (e.g. reject anything
    containing `-`) would falsely reject `ok-name`.
    """
    assert (
        _has_validate_safe_arg()
    ), "scripts/init_project.py: `_validate_safe_arg` not defined — fix not applied"

    proc = _run(["p", "--path", "./ok-name"], cwd=tmp_path)
    assert proc.returncode == 0, (
        f"legit relative path './ok-name' falsely rejected: rc={proc.returncode} "
        f"stderr={proc.stderr!r}"
    )
    out = tmp_path / "ok-name"
    assert (out / "feature-list.json").is_file(), f"feature-list.json missing at {out}"


# ------------------------------------------------------------------ B8-P2 ----
def test_b8_p2_reserved_flag_path_token_rejected(tmp_path: pathlib.Path) -> None:
    """Additional row: passing `--lang` as project_name (reserved keyword).

    Combined with fix-presence + targeted diagnostic — argparse alone may
    surface a generic `error: argument` message; the fix must produce a
    diagnostic mentioning either 'reserved' or 'argparse flag'.
    """
    assert (
        _has_validate_safe_arg()
    ), "scripts/init_project.py: `_validate_safe_arg` not defined — fix not applied"

    proc = _run(["--lang"], cwd=tmp_path)
    assert proc.returncode != 0, "reserved `--lang` accepted as project_name"
    assert not (tmp_path / "--lang").exists(), "rogue '--lang' dir created"
    stderr_low = (proc.stderr or "").lower()
    assert (
        "reserved" in stderr_low or "argparse flag" in stderr_low or "looks like" in stderr_low
    ), f"explicit guard diagnostic missing for --lang; stderr={proc.stderr!r}"
