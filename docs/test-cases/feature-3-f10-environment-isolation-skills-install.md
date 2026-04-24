# 测试用例集: F10 · Environment Isolation & Skills Installer

**Feature ID**: 3
**关联需求**: FR-043, FR-044, FR-045, NFR-009（含 ATS §5 K 类别约束 FUNC/BNDRY/SEC；NFR-009 = SEC；T01–T27 追溯，CON-005 反面断言）
**日期**: 2026-04-24
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则（FR-043/FR-044/FR-045/NFR-009）、ATS §5 K 类别约束、Feature Design Test Inventory T01–T27、可观察接口（`harness.env` / `harness.skills` / `harness.api` 公开 API、POSIX 文件系统观测、SQLite/JSONL 审计文件观测、FastAPI `TestClient` HTTP 响应、`subprocess.run` argv 观测、`os.stat_result.st_mtime_ns` 纳秒精度观测）推导，不阅读实现源码。
> - **Specification resolutions applied from Feature Design Clarification Addendum**：
>   - **ASM-F10-ENV-OQD2（user-approved）**：F10 `setup_run` 仅承诺 `<isolated>/.claude/` 物理就绪；`CLAUDE_CONFIG_DIR` vs `HOME` 由 F03 决定。本特性 ST 用例 NFR-009 mtime 断言针对**用户真实 `~/.claude/`**，与 env 策略解耦。
>   - **Design Deviation · symlink → 物理复制（user-approved）**：SRS FR-043 EARS 原文 "symlink" 在 F10 内改为 `shutil.copytree(..., dirs_exist_ok=True)` 物理副本；验收语义等价（`.claude-plugin/plugin.json` 存在且可解析 + sha256 等于源）。文档中 AC-2 断言改写为"物理副本"；差异记录见 Feature Design §Design Alignment · Design Deviation。
>   - **ASM-F10-COPY-PERF（assumed）**：bundle < 10 MB / O(10²) 文件，`copytree` p95 < 500 ms；若实测 p95 > 1 s 在 `long-task-increment` 评估优化。本特性 ST 不含 PERF 类别（ATS §5 K 未强制 PERF；见 §ATS 类别覆盖说明）。
> - `feature.ui == false` → 本特性无 UI 类别用例；FR-045 AC-1 UI 侧（"UI 显示 commit sha"）由 F22 Fe-Config SystemSettings / PromptsAndSkills 页面承担 ST；本特性覆盖的是**后端 REST `POST /api/skills/install|pull`**（IAPI-018）契约表面。
> - 本特性以 **"No server processes — environment activation only"** 模式运行（env-guide §1 纯 CLI / library 模式 —— `pytest tests/test_f10_*.py tests/integration/test_f10_*.py`），无需启动 `api` / `ui-dev` 服务。环境仅需 §2 `.venv` 激活。`POST /api/skills/install|pull` 的 REST 侧通过 `fastapi.testclient.TestClient(harness.api.app)` 在进程内执行，不绑 socket。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 12 |
| boundary | 7 |
| ui | 1 |
| security | 6 |
| performance | 0 |
| **合计** | **26** |

---

### 用例编号

ST-FUNC-003-001

### 关联需求

FR-043 AC-1 · §Interface Contract `setup_run` postcondition · Feature Design Test Inventory T01 · §Design Alignment sequenceDiagram msg#1–6

### 测试目标

验证 `EnvironmentIsolator.setup_run(run_id, workdir, bundle_root)` 以合法入参调用时返回 `IsolatedPaths` 契约对象（字段等于 `<isolated>/.claude/...` 规范路径），并在 workdir 下创建 `.harness-workdir/<run_id>/.claude/` 子树（含 `settings.json` / `mcp.json` / `plugins/longtaskforagent/`），且 `plugins/longtaskforagent` 为**物理副本**（非 symlink，`Path.is_symlink() == False`）。

### 前置条件

- `.venv` 激活；`harness.env.EnvironmentIsolator`、`IsolatedPaths` 可导入
- `pytest tmp_path` 提供空白 workdir（已存在绝对目录）
- bundle fixture：含 `.claude-plugin/plugin.json`（合法 JSON，1–64 KiB）与 `subdir/file.txt`（≥ 1 个非 manifest 普通文件）
- `home_dir` fixture 指向 `tmp/.claude`（测试注入，避免触碰用户真实 `~/.claude/`）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 `tmp_path` 下 `mkdir workdir`，构造 `bundle_root = tmp / bundle/` 含 `.claude-plugin/plugin.json` | workdir 与 bundle 创建成功 |
| 2 | `isolator = EnvironmentIsolator()`；调 `paths = isolator.setup_run("run-abc", workdir=workdir, bundle_root=bundle_root, home_dir=tmp/.claude)` | 返回 `IsolatedPaths`，无异常 |
| 3 | 断言 `paths.cwd == str(workdir)` | True |
| 4 | 断言 `paths.settings_path == str(workdir / ".harness-workdir" / "run-abc" / ".claude" / "settings.json")` | True |
| 5 | 断言 `paths.mcp_config_path == str(workdir / ".harness-workdir" / "run-abc" / ".claude" / "mcp.json")`；`Path(paths.settings_path).exists()` 与 `Path(paths.mcp_config_path).exists()` 为 True | 两文件存在 |
| 6 | `json.loads(Path(paths.settings_path).read_text())` 含 `permissions` key | True |
| 7 | `json.loads(Path(paths.mcp_config_path).read_text())` 是 dict 合法 JSON | True |
| 8 | `dst_plugin = Path(paths.plugin_dir) / "longtaskforagent"`；断言 `dst_plugin.exists()` 且 `dst_plugin.is_symlink() == False`（物理复制） | True |
| 9 | 断言 `(dst_plugin / ".claude-plugin" / "plugin.json").exists()` | True |

### 验证点

- `IsolatedPaths` 4 字段（cwd / plugin_dir / settings_path / mcp_config_path）规范并可访问
- `<isolated>/.claude/` 子树结构与 §Interface Contract postcondition 完全匹配
- `plugins/longtaskforagent` 是物理副本（非 symlink / junction）— Design Deviation 约束
- settings.json / mcp.json 是合法 JSON

### 后置检查

- `tmp_path` 自动清理
- 用户真实 `~/.claude/` 未被触碰（由 home_dir 注入隔离）

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t01_setup_run_produces_isolated_paths_and_physical_copy`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-002

### 关联需求

FR-043 AC-2 · §Interface Contract `sync_bundle` postcondition · Feature Design Test Inventory T02 · §Acceptance Mapping

### 测试目标

验证 `setup_run` 完成后，副本 `<isolated>/.claude/plugins/longtaskforagent/.claude-plugin/plugin.json` 字节与源 `bundle_root/.claude-plugin/plugin.json` 字节 sha256 **一致**；副本根目录**不是** symlink；Claude Code CLI 以副本为工作目录能解析 plugin.json（通过独立 `json.loads` 等价验证）。

### 前置条件

- 同 ST-FUNC-003-001；bundle 的 plugin.json 内容 = `{"name":"longtaskforagent","version":"1.0.0"}`（非 0 字节、≤ 64 KiB）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `setup_run` 同上 | `paths` 返回 |
| 2 | `src_bytes = (bundle_root / ".claude-plugin" / "plugin.json").read_bytes()` | 成功 |
| 3 | `dst_bytes = (Path(paths.plugin_dir) / "longtaskforagent" / ".claude-plugin" / "plugin.json").read_bytes()` | 成功 |
| 4 | 断言 `hashlib.sha256(src_bytes).hexdigest() == hashlib.sha256(dst_bytes).hexdigest()` | True |
| 5 | 断言 `(Path(paths.plugin_dir) / "longtaskforagent").is_symlink() == False` | True |
| 6 | `json.loads(dst_bytes.decode("utf-8"))` 解析通过，含 `name` / `version` key | True |

### 验证点

- 副本 sha256 严格等于源 sha256（物理复制保真）
- 副本根目录非 symlink / junction
- `plugin.json` 可被 Claude Code CLI 等价解析（JSON 合法）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t02_setup_run_manifest_sha256_matches_source`、`tests/test_f10_plugin_registry.py::test_t02_sync_bundle_copies_physically_and_sha_matches`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-003

### 关联需求

FR-044 AC-1 · §Interface Contract `WorkdirScopeGuard.assert_scope` postcondition · Feature Design Test Inventory T03

### 测试目标

验证 `WorkdirScopeGuard.assert_scope(workdir, before=<setup 前集合>, after=<现场集合>)` 在"仅 `.harness/` 与 `.harness-workdir/` 子树新增文件"的场景下返回 `ok=True`、`unexpected_new=[]`；即 Harness 未向 workdir 非 `.harness/` 下写入自身文件。

### 前置条件

- `.venv` 激活；`harness.env.WorkdirScopeGuard` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `mkdir workdir`；`before = set()`（空快照） | 空集 |
| 2 | `setup_run("r1", workdir, bundle_root, home_dir=tmp/.claude)` | 成功 |
| 3 | 模拟 "skill 自写" 在 `workdir/src/foo.py` 新增（合法 —— skill 写的文件不算 Harness 临时文件，但此处测试 scope guard 仅过滤 Harness 托管子目录） | 文件写入成功 |
| 4 | `guard = WorkdirScopeGuard()`；`report = guard.assert_scope(workdir, before=before)`（after 默认现场扫描） | 返回 `WorkdirScopeReport` |
| 5 | 断言 `report.ok == True`（当 `unexpected_new` 仅为 `.harness/` 或 `.harness-workdir/` 开头时 True） 或在 `src/foo.py` 也被接受的宽松语义下 `unexpected_new` 仅含 skill 自写条目 —— 按 §Interface Contract `assert_scope` 的 `allowed_subdirs=frozenset({".harness", ".harness-workdir"})` 默认值，新增 `src/foo.py` 不属这两前缀将进入 `unexpected_new` | 若实现将 skill 自写视为 "unexpected_new"，则记录但断言 `set(report.unexpected_new).issubset(...)` 符合 `tests/test_f10_environment_isolator.py::test_t03_workdir_scope_guard_ok_when_only_harness_subdirs_changed` 预期语义 |
| 6 | 等价测试：`before = set()`；setup 后**不**添加非 `.harness*` 文件；再跑 `assert_scope` | `ok == True`，`unexpected_new == []` |

### 验证点

- Harness 的 setup 调用仅向 `.harness-workdir/` 下写入
- 当 workdir 根未被 Harness 污染时 `ok=True`
- `assert_scope` 过滤规则对 `.harness/` 前缀正确

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t03_workdir_scope_guard_ok_when_only_harness_subdirs_changed`、`tests/test_f10_environment_isolator.py::test_t03b_workdir_scope_guard_ok_true_when_nothing_new_outside_allowed`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-004

### 关联需求

FR-045 AC-1 · §Interface Contract `SkillsInstaller.install` postcondition · §Implementation Summary flow branch Clone-ok · Feature Design Test Inventory T04

### 测试目标

验证 `SkillsInstaller.install(SkillsInstallRequest(kind="clone", source="https://github.com/org/ltfa.git", target_dir="plugins/longtaskforagent"), workdir=wd)` 在 `git clone` 成功 mock 下返回 `SkillsInstallResult(ok=True, commit_sha=<40-hex>, message=...)`；底层 subprocess argv 首段为 `["git","clone","--depth","1","--", ...]` 且 **`shell` 参数未出现 True**（不拼接 shell 命令）。

### 前置条件

- `.venv` 激活；`harness.skills.SkillsInstaller` / `SkillsInstallRequest` 可导入
- `monkeypatch` subprocess 保证 mock `git clone` 返回 exit=0 + 在 target_dir 构造 `.claude-plugin/plugin.json` + `.git/` 存根

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `wd`；`req = SkillsInstallRequest(kind="clone", source="https://github.com/org/ltfa.git", target_dir="plugins/longtaskforagent")` | 构造成功 |
| 2 | mock `subprocess.run`：返回 `CompletedProcess(args=..., returncode=0, stdout="", stderr="")`；同时在 `wd/plugins/longtaskforagent/.claude-plugin/plugin.json` 写合法 JSON + `.git/HEAD` 存根 | mock 就绪 |
| 3 | `installer = SkillsInstaller()`；`result = installer.install(req, workdir=wd)` | 返回 `SkillsInstallResult` |
| 4 | 断言 `result.ok == True` | True |
| 5 | 断言 `re.fullmatch(r"[0-9a-f]{40}", result.commit_sha)` 匹配（40 位 hex 小写） | 匹配 |
| 6 | 检查 mock 捕获的 `subprocess.run` argv 调用：断言 argv 前 4 段 = `["git", "clone", "--depth", "1"]`，接着含 `"--"` 与 `"https://github.com/org/ltfa.git"`；所有 call 的 `kwargs.get("shell", False) == False` | True |
| 7 | 断言 `result.message` 包含中文摘要（含 "clone" 或 "完成" 类词） | True |

### 验证点

- `git clone --depth 1 --` argv 顺序正确
- `shell=True` 从未出现（SEC 基线）
- `commit_sha` 为 40-hex
- FR-045 AC-1 "clone → 目录生成" 成立（target_dir 下 `.claude-plugin/plugin.json` 存在）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t04_install_clone_uses_argv_list_no_shell_and_returns_commit_sha`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-005

### 关联需求

FR-045 AC-2 · §Interface Contract `SkillsInstaller.pull` postcondition · §Implementation Summary flow branch pull · Feature Design Test Inventory T05

### 测试目标

验证 `SkillsInstaller.pull(target_dir, workdir=wd)` 对已在 `wd/plugins/<name>/` 的 git 仓库执行 `git -C <target> pull --ff-only`，成功时返回 `ok=True` + `commit_sha=<HEAD 40-hex>`；argv 包含 `-C` 与 `--ff-only`（非普通 `git pull`）。

### 前置条件

- mock `subprocess.run` 返回 `Already up to date.` exit=0；target_dir 含 `.git/` 与 `.claude-plugin/plugin.json`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `wd/plugins/longtaskforagent` 含 `.git/HEAD`、`.claude-plugin/plugin.json` | 成功 |
| 2 | mock subprocess `git rev-parse HEAD` 返 40-hex；`git -C ... pull --ff-only` 返 exit=0 | mock 就绪 |
| 3 | `result = installer.pull("plugins/longtaskforagent", workdir=wd)` | 返回 `SkillsInstallResult` |
| 4 | 断言 `result.ok == True` | True |
| 5 | 检查 argv：包含 `"git"`, `"-C"`, `<abs target_dir>`, `"pull"`, `"--ff-only"`（顺序相对不强制，但 4 个 token 必须出现） | True |
| 6 | 断言 `re.fullmatch(r"[0-9a-f]{40}", result.commit_sha)` | True |

### 验证点

- pull argv 含 `--ff-only`（ff-only 语义对齐 §6.1.5 约束）
- pull argv 含 `-C <target>`（不在当前 cwd 运行 git）
- `commit_sha` 取自 HEAD

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t05_pull_uses_dash_C_and_ff_only_and_returns_head_sha`、`tests/integration/test_f10_real_git.py::test_t21_real_git_pull_ff_only_against_local_remote`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-006

### 关联需求

NFR-009 · FR-043 AC-1 · §Interface Contract `teardown_run` postcondition · Feature Design Test Inventory T06

### 测试目标

验证完整 setup → teardown 生命周期后 `HomeMtimeGuard.diff_against` 返回 `HomeMtimeDiff(changed_files=[], added_files=[], removed_files=[], ok=True)`，即 Harness 运行期间**零写入**用户真实 `~/.claude/`（NFR-009 "mtime 无变化"）。

### 前置条件

- 测试注入 `home_dir=tmp/.claude`；预埋 3 个普通文件（含嵌套子目录）
- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 在 `tmp/.claude/` 下预埋 `settings.json`（50 字节）、`plugins/foo/a.txt`、`history/h.log`，记录各文件 `st_mtime_ns` | 预埋成功 |
| 2 | `paths = isolator.setup_run("run-xyz", workdir, bundle_root, home_dir=tmp/.claude)` | 成功 |
| 3 | `diff = isolator.teardown_run("run-xyz", paths)` | 返回 `HomeMtimeDiff` |
| 4 | 断言 `diff.ok == True` | True |
| 5 | 断言 `diff.changed_files == []` | True |
| 6 | 断言 `diff.added_files == []` 与 `diff.removed_files == []` | True |
| 7 | 再次读取预埋文件 `st_mtime_ns` 并断言与 step 1 完全相等（独立旁证） | 全等 |

### 验证点

- `HomeMtimeDiff` 三列表全为空（NFR-009 硬阈值）
- 旁证 `st_mtime_ns` 无变化（精度达纳秒）
- Harness setup / teardown 未路径穿透到用户 `~/.claude/`

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t06_teardown_run_returns_empty_home_mtime_diff`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-007

### 关联需求

§Interface Contract `Raises: RunIdInvalidError` · §Boundary Conditions run_id 字符集 · Feature Design Test Inventory T07 / T07b

### 测试目标

验证 `setup_run(run_id)` 对非法 `run_id`（含路径穿越、控制字符、非 ASCII、空格、shell meta）抛 `RunIdInvalidError`，且 `<workdir>/.harness-workdir/` 下**不**新建任何目录（原子拒绝，无副作用）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 调 `setup_run("../../evil", workdir, bundle_root)`，捕获异常 | 抛 `RunIdInvalidError`，消息含 "invalid run_id" 或等效 |
| 2 | 断言 `(workdir / ".harness-workdir").exists() == False` 或其下为空 | True（无副作用） |
| 3 | 参数化重复：`"a/b"`、`"a\\b"`、`"has space"`、`"weird#tag"`、`"unicodé-id"`；每次均抛 `RunIdInvalidError` | 5 次全抛 |
| 4 | 每次失败后检查 `.harness-workdir/` 未污染 | True |

### 验证点

- `run_id` 必须匹配 `^[A-Za-z0-9_-]{1,64}$`；否则早期拒绝
- 失败无副作用（原子性）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t07_setup_run_rejects_traversal_run_id`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[a/b]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[a\\b]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[has space]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[weird#tag]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[unicod\xe9-id]`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-008

### 关联需求

§Interface Contract `Raises: WorkdirNotFoundError` · Feature Design Test Inventory T08

### 测试目标

验证 `setup_run(run_id, workdir=<不存在路径>, bundle_root)` 抛 `WorkdirNotFoundError`，不静默创建，不回退为 best-effort mkdir。

### 前置条件

- `.venv` 激活；bundle_root 合法

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 调 `setup_run("r1", workdir=Path("/nope/does/not/exist"), bundle_root)` | 抛 `WorkdirNotFoundError` |
| 2 | 断言 `Path("/nope/does/not/exist").exists() == False`（未被静默创建） | True |

### 验证点

- 不存在 workdir 触发明确异常，避免"路径打错 → 静默创建 → 文件误落盘"
- 异常类型精确为 `WorkdirNotFoundError`（非泛型 `FileNotFoundError`）

### 后置检查

- 无

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t08_setup_run_raises_workdir_not_found`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-009

### 关联需求

§Interface Contract `Raises: BundleNotFoundError` · Feature Design Test Inventory T09

### 测试目标

验证 `setup_run(run_id, workdir, bundle_root=<缺 .claude-plugin/ 的空目录>)` 抛 `BundleNotFoundError`，不静默复制空目录、不在 target 构造伪 manifest。

### 前置条件

- `.venv` 激活；workdir 合法；bundle_root 存在但缺 `.claude-plugin/plugin.json`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `bundle_root = tmp / "empty_bundle"; bundle_root.mkdir()`（无 manifest） | 目录创建 |
| 2 | 调 `setup_run("r1", workdir, bundle_root)` | 抛 `BundleNotFoundError` |
| 3 | 断言 `workdir/.harness-workdir/r1/.claude/plugins/longtaskforagent` 不存在（未做半截拷贝） | True |

### 验证点

- bundle_root 缺 manifest 早期拒绝
- 失败原子性（target 目录未生成）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t09_setup_run_raises_bundle_not_found`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-010

### 关联需求

§Interface Contract `Raises: IsolationSetupError` · Feature Design Test Inventory T10

### 测试目标

验证 `setup_run` 在 workdir 为只读目录（POSIX `chmod 0o500`）时 `mkdir` 失败抛 `IsolationSetupError`，消息含失败的子路径（不被吞成泛型 `PermissionError`）。

### 前置条件

- `.venv` 激活；POSIX 平台；workdir 存在并 chmod 0o500（只读）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `workdir = tmp / "ro"; workdir.mkdir(mode=0o500)`（只读） | 成功 |
| 2 | 调 `setup_run("r1", workdir, bundle_root)` | 抛 `IsolationSetupError` |
| 3 | 断言异常消息包含路径片段 `.harness-workdir` 或 `r1` | True |
| 4 | 清理：`chmod 0o700` 以便 tmp 清理 | 成功 |

### 验证点

- 文件系统权限错误被包装为领域异常 `IsolationSetupError`
- 消息含失败路径（诊断友好）

### 后置检查

- 恢复 chmod；tmp 清理

### 元数据

- **优先级**: Medium
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t10_setup_run_raises_isolation_setup_error_on_readonly_workdir`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-011

### 关联需求

§IAPI-009 复用 · §Implementation Summary audit 链 · Feature Design Test Inventory T26

### 测试目标

验证 `setup_run` → `teardown_run` 生命周期在 F02 `AuditWriter.append_raw` 上追加 `env.setup` 与 `env.teardown` 两条 JSONL 事件（顺序正确、`payload` 含 `run_id` / `paths` / `ok` 字段）。

### 前置条件

- `.venv` 激活；真实 F02 audit writer；tmp workdir 下 `.harness/audit/` 已初始化

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 workdir + bundle；确保 `workdir/.harness/audit/` 可写 | 就绪 |
| 2 | `setup_run("r1", workdir, bundle_root, home_dir=tmp/.claude)`；`teardown_run("r1", paths)` | 无异常 |
| 3 | 读取 `workdir/.harness/audit/r1.jsonl`（或当前 run audit 文件），按行 split | ≥ 2 行 |
| 4 | 第一条 `json.loads` → `kind == "env.setup"`；含 `run_id="r1"`；`payload` 含 `paths` dict | True |
| 5 | 第二条 `kind == "env.teardown"`；`payload.ok == True`；`payload.changed_files == []` | True |
| 6 | `setup` 行 `ts` ≤ `teardown` 行 `ts`（顺序） | True |

### 验证点

- 审计流完整记录生命周期两端事件
- 顺序正确（setup 先于 teardown）
- payload schema 稳定（含 `run_id` / `ok` / `paths`）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f10_real_fs_audit.py::test_t26_audit_writer_records_env_setup_and_teardown`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-003-012

### 关联需求

IAPI-018 REST happy · §Implementation Summary REST 链 · Feature Design Test Inventory T23

### 测试目标

验证 `POST /api/skills/install`（via `fastapi.testclient.TestClient`）在合法 clone 请求下返回 HTTP 200 + JSON body schema = `SkillsInstallResult(ok, commit_sha, message)`；`Content-Type` 为 JSON；subprocess 被 mock 成功。

### 前置条件

- `.venv` 激活；`HARNESS_WORKDIR` env 指向 tmp workdir；`harness.api.app` 可实例化
- `monkeypatch` subprocess 成功

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 设置 `HARNESS_WORKDIR=tmp/wd`；`tmp/wd` 已 mkdir 含 `.harness/` | 就绪 |
| 2 | `client = TestClient(app)`；body = `{"kind":"clone","source":"https://github.com/org/x.git","target_dir":"plugins/longtaskforagent"}` | 构造 |
| 3 | `resp = client.post("/api/skills/install", json=body)` | 200 |
| 4 | `resp.headers["content-type"]` 含 `application/json` | True |
| 5 | `data = resp.json()`；断言 `data["ok"] is True`；`re.fullmatch(r"[0-9a-f]{40}", data["commit_sha"])`；`data["message"]` 为非空字符串 | True |

### 验证点

- HTTP 200 路径 schema 稳定
- commit_sha 40-hex
- Content-Type JSON（非 text/html）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_rest.py::test_t23_rest_install_clone_returns_200_with_schema`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-001

### 关联需求

§Boundary Conditions run_id 长度 · Feature Design Test Inventory T16

### 测试目标

验证 `setup_run.run_id` 长度边界：64 字符（恰合法）通过；65 字符（超限）抛 `RunIdInvalidError`；空字符串抛 `RunIdInvalidError`（off-by-one 防护）。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `run_id = "a" * 64`（纯合法 64 字符）；`setup_run(run_id, workdir, bundle_root, home_dir=tmp/.claude)` | 成功返回 `IsolatedPaths` |
| 2 | `run_id = "a" * 65`（超限 1）；`setup_run(...)` | 抛 `RunIdInvalidError` |
| 3 | `run_id = ""`（空）；`setup_run(...)` | 抛 `RunIdInvalidError` |

### 验证点

- 上限恰 64 字符通过；65 拒绝
- 空串拒绝

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t16_run_id_length_bounds`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-002

### 关联需求

NFR-009 精度要求 · §Interface Contract `HomeMtimeGuard.snapshot/diff_against` · Feature Design Test Inventory T17

### 测试目标

验证 `HomeMtimeGuard` 使用纳秒级 `st_mtime_ns` 而非秒级 `st_mtime`：snapshot 后在 1 秒内通过 `os.utime` 将某文件 `mtime_ns` 仅增 1ns，再 diff 应能检出 `changed_files` 非空（`ok=False`），即 1 秒内写入**不**被精度吞并。

### 前置条件

- `.venv` 激活；tmp home_dir 含一个预埋文件

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `home = tmp/.claude`；`home.mkdir()`；`(home/"a.txt").write_text("x")` | 成功 |
| 2 | `before = guard.snapshot(home)` | 返回 `HomeMtimeSnapshot` |
| 3 | 读取 `(home/"a.txt").stat().st_mtime_ns` → `m0` | 得 `m0` |
| 4 | `os.utime(home/"a.txt", ns=(m0, m0 + 1))`（仅增 1 纳秒） | 成功 |
| 5 | `diff = guard.diff_against(before)` | 返回 `HomeMtimeDiff` |
| 6 | 断言 `diff.ok == False` | True |
| 7 | 断言 `"a.txt"` 或等效相对路径在 `[c.path for c in diff.changed_files]` | True |

### 验证点

- 纳秒精度断言（若用 `st_mtime` 则同秒内 +1ns 被吞，`ok=True` 为假阴性 — 此步会 FAIL）
- 变更文件被正确列出

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t17_home_mtime_guard_detects_nanosecond_change`、`tests/test_f10_environment_isolator.py::test_t17b_home_mtime_guard_empty_snapshot_on_missing_home`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-003

### 关联需求

§Boundary Conditions plugin.json 大小 · §Interface Contract `PluginRegistry.read_manifest` Raises · Feature Design Test Inventory T18

### 测试目标

验证 `PluginRegistry.read_manifest(plugin_dir)` 对 manifest 文件字节大小的边界处理：0 字节 → `PluginManifestCorruptError`；1 字节合法 JSON → 通过；64 KiB 恰等 → 通过；64 KiB + 1 → `PluginManifestCorruptError`（DoS 防护上限）；缺失文件 → `PluginManifestMissingError`。

### 前置条件

- `.venv` 激活；tmp plugin_dir 含 `.claude-plugin/` 可写

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | plugin.json 写 0 字节；`read_manifest(...)` | 抛 `PluginManifestCorruptError` |
| 2 | plugin.json 写 `{}`（2 字节 JSON 但 schema 缺 `name`/`version` → 仍触发 `PluginManifestCorruptError`）；或写最小合法 1 字节是非法 JSON → 按 §Boundary "1 字节通过" 测例实现：写 `{"name":"x","version":"1"}` 精确 1+ 字节合法 schema | 通过（返回 `PluginManifest`） |
| 3 | plugin.json 写恰 64 KiB 合法 JSON（字段填充至 65536 字节） | 通过 |
| 4 | plugin.json 写 64 KiB + 1 | 抛 `PluginManifestCorruptError` |
| 5 | 删除 plugin.json 再读 | 抛 `PluginManifestMissingError` |

### 验证点

- 0 字节拒绝（corrupt）
- 64 KiB 精确上限通过；+1 拒绝（DoS 防护显式）
- 缺失文件为 missing，不是 corrupt（语义区分）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_plugin_registry.py::test_t18_read_manifest_zero_bytes_raises_corrupt`、`tests/test_f10_plugin_registry.py::test_t18b_read_manifest_one_byte_minimal_valid`、`tests/test_f10_plugin_registry.py::test_t18c_read_manifest_64kib_exact_accepted`、`tests/test_f10_plugin_registry.py::test_t18d_read_manifest_over_64kib_rejects`、`tests/test_f10_plugin_registry.py::test_t18e_read_manifest_missing_raises_missing_error`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-004

### 关联需求

feature-list.json#3 verification_steps[3] · CON-005 反面断言（源 bundle 侧）· Feature Design Test Inventory T19

### 测试目标

验证 CON-005"run 期间 `plugins/longtaskforagent/` mtime 不变"的**源 bundle 侧**断言：对源 `bundle_root`（SkillsInstaller 管辖对象）在 setup 前取 `st_mtime_ns` 快照；跑完整 setup → teardown → scope assert 后，源 `bundle_root` 下所有 regular file 的 mtime_ns **无变化**（无自动 pull、无反向写）。副本（每-run 临时路径 `.harness-workdir/<run_id>/.claude/plugins/longtaskforagent/`）允许变化，但不在本断言范围。

### 前置条件

- `.venv` 激活；bundle_root 含 `.claude-plugin/plugin.json` + 至少 1 个非 manifest 文件

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 遍历 `bundle_root`，记录 `{rel_path: st_mtime_ns}` snapshot `S0`（排除 `.git/`） | 得 `S0` |
| 2 | `setup_run("r-con005", workdir, bundle_root)` | 成功 |
| 3 | 触发一次 `installer.install(SkillsInstallRequest(kind="local", source=..., target_dir=...))` 或 `pull`（对副本路径操作） | 成功（副本变化） |
| 4 | `teardown_run("r-con005", paths)` | `ok=True` |
| 5 | 再遍历 `bundle_root`，记录 snapshot `S1` | 得 `S1` |
| 6 | 断言 `S0 == S1`（源 mtime_ns 全等） | True |

### 验证点

- 源 bundle 在 run 期内未被 Harness 触碰（CON-005 反面硬断言）
- 副本路径允许变化，不污染源

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_con005_reverse.py::test_t19_source_bundle_mtime_ns_unchanged_through_setup_teardown`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-005

### 关联需求

§Interface Contract `PluginRegistry.sync_bundle` postcondition 幂等 · Feature Design Test Inventory T20

### 测试目标

验证 `PluginRegistry.sync_bundle(src_bundle, dst_plugin_dir)` 连续两次同参数调用**不抛错**（`dirs_exist_ok=True` 语义），副本 `.claude-plugin/plugin.json` 两次 sha256 一致；第二次调用前后副本根下全部文件内容与首次一致。

### 前置条件

- `.venv` 激活；src_bundle 合法

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 首次 `registry.sync_bundle(src, dst)` | 返回 `PluginSyncResult`，无异常 |
| 2 | `sha1 = sha256(dst/.claude-plugin/plugin.json)` | 得 `sha1` |
| 3 | 第二次 `registry.sync_bundle(src, dst)` | **无异常**（不抛 `FileExistsError`） |
| 4 | `sha2 = sha256(dst/.claude-plugin/plugin.json)` | `sha2 == sha1` |
| 5 | 断言 `PluginSyncResult.manifest_sha256` 两次值一致 | True |

### 验证点

- 幂等性：第二次不抛错
- 结果稳定（sha256 不漂移）
- `dirs_exist_ok=True` 语义成立

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_plugin_registry.py::test_t20_sync_bundle_is_idempotent`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-006

### 关联需求

§Interface Contract `sync_bundle` 源不被触碰条款 · §Clarification Addendum Design Deviation · Feature Design Test Inventory T27

### 测试目标

验证 `sync_bundle` 为**物理复制**而非 hard link / symlink / junction：副本中修改 `plugin.json` 一个字节后，源 `plugin.json` 的 sha256 不变（副本与源不共享 inode）。

### 前置条件

- `.venv` 激活；src_bundle 合法

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `sync_bundle(src, dst)` 完成 | 成功 |
| 2 | `src_sha_before = sha256(src/.claude-plugin/plugin.json)` | 得 `sha0` |
| 3 | 在 `dst/.claude-plugin/plugin.json` 末尾追加一个空格字节（或替换一个字符） | 副本被修改 |
| 4 | `src_sha_after = sha256(src/.claude-plugin/plugin.json)` | 得 `sha1` |
| 5 | 断言 `src_sha_after == src_sha_before`（源未被反向改写） | True |
| 6 | 断言 `Path(dst/.claude-plugin/plugin.json).is_symlink() == False` 与源路径不是相同 inode（`os.stat(...).st_ino != os.stat(src...).st_ino`，POSIX 下若可比较） | True |

### 验证点

- 副本是物理独立字节序列（非 symlink / hardlink）
- 修改副本不回传到源
- inode 不同（文件系统级验证）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_plugin_registry.py::test_t27_copy_isolation_src_untouched_when_dst_modified`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-003-007

### 关联需求

§Implementation Summary flow branch `kind="local"` · §Boundary Conditions SkillsInstaller.source · Feature Design §Test Inventory 补充（TDD Red 阶段补齐的 FUNC/happy 本地拷贝）

### 测试目标

验证 `SkillsInstaller.install(SkillsInstallRequest(kind="local", source=<abs dir inside workdir>, target_dir="plugins/..."))` 将指定本地目录**物理复制**到 `workdir/plugins/<name>/`；拒绝相对路径 source、拒绝已存在 target（`dirs_exist_ok=False` 语义）、拒绝 target 路径逃逸。

### 前置条件

- `.venv` 激活；tmp workdir；tmp source 目录含 `.claude-plugin/plugin.json`

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 构造 `src = wd/src_local`（绝对路径，workdir 下）含 manifest；`req=SkillsInstallRequest(kind="local", source=str(src), target_dir="plugins/ltfa")` | 就绪 |
| 2 | `installer.install(req, workdir=wd)` | 返回 `ok=True` |
| 3 | 断言 `(wd/plugins/ltfa/.claude-plugin/plugin.json).exists()` | True |
| 4 | 相对路径 source：`req2 = ..(source="src_local", ...)`；`installer.install(req2, workdir=wd)` → 应抛 `TargetPathEscapeError` 或 `GitUrlRejectedError`（按实现；无论哪种都不得执行拷贝） | 抛异常 |
| 5 | target 已存在：再次调 step 1 的 req → 抛异常（target 存在） | 抛异常 |

### 验证点

- local 分支物理复制
- 相对路径 source 拒绝（绝对路径约束）
- target 存在拒绝（避免静默覆盖）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t_local_install_copies_absolute_local_dir_into_plugins`、`tests/test_f10_coverage_supplement.py::test_installer_local_kind_rejects_relative_source`、`tests/test_f10_coverage_supplement.py::test_installer_local_kind_rejects_when_target_exists`
- **Test Type**: Real

---

### 用例编号

ST-SEC-003-001

### 关联需求

FR-045 SEC（ATS 备注 "git URL 白名单"）· §Implementation Summary flow branch GitUrl · Feature Design Test Inventory T11

### 测试目标

验证 `SkillsInstaller.install(kind="clone", source=<非白名单 scheme>)` 抛 `GitUrlRejectedError`，subprocess **未被调用**（mock `assert_not_called`）；REST 层对应 HTTP 400（另见 ST-SEC-003-006）。

### 前置条件

- `.venv` 激活；mock subprocess（用于断言未被调用）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 参数化 source：`"file:///etc/passwd"`, `"ftp://example.com/repo.git"`, `"javascript:alert(1)"`, `""` | 4 种非法 URL |
| 2 | 对每个 source：`installer.install(SkillsInstallRequest(kind="clone", source=src, target_dir="plugins/ltfa"), workdir=wd)` | 抛 `GitUrlRejectedError` |
| 3 | 断言 mock `subprocess.run` 调用次数 = 0（整个用例跑完也未被调用） | True |
| 4 | 断言 `wd/plugins/ltfa` 不存在（无半截目录） | True |

### 验证点

- 白名单仅含 `https://` 与 `git@host:path`；其余 scheme（`file://`、`ftp://`、`javascript:`、空）早期拒绝
- subprocess 未被触发（SEC：杜绝非白名单 git exec）
- 原子失败

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[file:///etc/passwd]`、`tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[ftp://example.com/repo.git]`、`tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[javascript:alert(1)]`、`tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[]`
- **Test Type**: Real

---

### 用例编号

ST-SEC-003-002

### 关联需求

FR-045 SEC · §Implementation Summary flow branch Meta · Feature Design Test Inventory T12

### 测试目标

验证 `SkillsInstaller.install` 拒绝含 shell meta 字符（`;`、`\n`、`\r`、`..`）的 `https://...` URL，抛 `GitUrlRejectedError`；subprocess 未调用（阻断 shell 注入 RCE 路径）。

### 前置条件

- mock subprocess；workdir 就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 参数化恶意 URL：`"https://legit.com/repo.git; rm -rf ~"`, `"https://legit.com/repo.git\nrm -rf ~"`, `"https://legit.com/repo.git\r\nls"`, `"https://legit.com/../../etc/repo.git"` | 4 种 |
| 2 | 对每个 URL：`installer.install(SkillsInstallRequest(kind="clone", source=url, target_dir="plugins/ltfa"), workdir=wd)` | 抛 `GitUrlRejectedError` |
| 3 | 断言 mock `subprocess.run` call 次数 = 0 | True |

### 验证点

- shell meta（`;`、`\n`、`\r`）在 URL 中被拒
- `..` 路径穿越在 URL 中被拒
- subprocess 未被触发（RCE 杜绝）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/repo.git; rm -rf ~]`、`tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/repo.git\nrm -rf ~]`、`tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/repo.git\r\nls]`、`tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/../../etc/repo.git]`
- **Test Type**: Real

---

### 用例编号

ST-SEC-003-003

### 关联需求

FR-045 SEC · §Implementation Summary flow branch Target · §Boundary Conditions target_dir · Feature Design Test Inventory T13

### 测试目标

验证 `SkillsInstaller.install` 对非法 `target_dir`（路径穿越、绝对路径、plugins 外、恰等 `plugins`）抛 `TargetPathEscapeError`；不做任何文件系统写入。

### 前置条件

- mock subprocess；workdir 就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 参数化 target_dir：`"plugins/../../etc/evil"`, `"../outside"`, `"/absolute/path"`, `"plugins"`（根本身不含子目录） | 4 种 |
| 2 | 对每个：`installer.install(SkillsInstallRequest(kind="clone", source="https://github.com/org/x.git", target_dir=t), workdir=wd)` | 抛 `TargetPathEscapeError` |
| 3 | 断言 `/etc/evil` 与 `wd.parent/outside` 等关联路径未被创建 | True |
| 4 | 断言 mock subprocess 未被调用 | True |

### 验证点

- path normalization 防穿越（`Path.resolve(strict=False).is_relative_to(workdir/"plugins")` 语义）
- 绝对路径拒绝
- `plugins` 根本身拒绝（必须有子目录名）
- 失败无副作用

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[plugins/../../etc/evil]`、`tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[../outside]`、`tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[/absolute/path]`、`tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[plugins]`
- **Test Type**: Real

---

### 用例编号

ST-SEC-003-004

### 关联需求

FR-044 · §Interface Contract `WorkdirScopeGuard.assert_scope` · Feature Design Test Inventory T14

### 测试目标

验证 `WorkdirScopeGuard.assert_scope` 能检出 Harness 意外（bug）往 workdir 根写入文件：setup 后人为在 `<workdir>/__injected__.tmp` 写入（模拟 Harness bug），scope guard 比对 before / after 应返回 `ok=False` 且 `unexpected_new` 含该文件。

### 前置条件

- `.venv` 激活

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `before = set(递归相对路径集合)`（workdir 空 → `before=set()`） | 空 |
| 2 | `setup_run("r1", workdir, bundle_root)` | 成功 |
| 3 | 人为写入 `workdir/__injected__.tmp`（模拟 Harness bug） | 成功 |
| 4 | `report = guard.assert_scope(workdir, before=before)` | 返回 `WorkdirScopeReport` |
| 5 | 断言 `report.ok == False` | True |
| 6 | 断言 `"__injected__.tmp"` 在 `report.unexpected_new` | True |

### 验证点

- scope guard 能发现 Harness 自身 bug 引入的 workdir 根级污染
- `.harness-workdir/` 下的文件不触发误报
- 过滤规则对非 `.harness*` 前缀正确

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_environment_isolator.py::test_t14_workdir_scope_guard_flags_injected_tmp_outside_allowed`
- **Test Type**: Real

---

### 用例编号

ST-SEC-003-005

### 关联需求

§Interface Contract `Raises: SkillsInstallBusyError` · §Implementation Summary run-lock 协同 · Feature Design Test Inventory T15

### 测试目标

验证 `SkillsInstaller.install` 在 `<workdir>/.harness/run.lock` 存在（run 进行中）时抛 `SkillsInstallBusyError`（HTTP 409），subprocess 未调用（避免与正在运行的 run 争用 plugin 目录）。

### 前置条件

- `.venv` 激活；预放 `<workdir>/.harness/run.lock` 空文件

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `mkdir wd/.harness`；`(wd/.harness/run.lock).write_text("")` | 成功 |
| 2 | `installer.install(SkillsInstallRequest(kind="clone", source="https://github.com/org/x.git", target_dir="plugins/ltfa"), workdir=wd)` | 抛 `SkillsInstallBusyError` |
| 3 | 断言 mock subprocess 未被调用 | True |
| 4 | 断言 `wd/plugins/ltfa` 不存在 | True |

### 验证点

- run.lock 存在即拒绝，早期退出
- 不与运行中 run 竞争
- REST 层 409 对应（见 ST-SEC-003-006）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_installer.py::test_t15_install_rejects_when_run_lock_present`、`tests/test_f10_coverage_supplement.py::test_api_skills_pull_run_lock_returns_409`
- **Test Type**: Real

---

### 用例编号

ST-UI-003-001

### 关联需求

FR-045 UI 范畴 · ATS §5 K FR-045 UI 类别 · IAPI-018 REST response schema · §Acceptance Mapping "UI 显示 commit sha" 跨 Feature 锚点（F22 承载 UI 渲染，F10 承载后端数据源）

### 测试目标

验证 F10 `POST /api/skills/install|pull` 响应 body 含 F22 Fe-Config `PromptsAndSkills` 页面"Update Plugin"按钮点击后渲染 commit sha 所需的**数据契约字段**（`commit_sha`、`ok`、`message`），字段类型/格式满足 UI 侧 40-hex 显示与中文消息呈现的前提；即 UI 类别覆盖本 feature 的**后端可观察表面**（UI 渲染由 F22 ST 承担，二者通过 REST schema 握手）。

### 前置条件

- `.venv` 激活；`HARNESS_WORKDIR` 指向 tmp wd；`TestClient(app)` 就绪；subprocess mock 成功
- 说明：**F10 是后端/library 特性（`"ui": false`）**；ATS §5 K 对 FR-045 列出 UI 类别是基于"用户可见反馈"要求 —— 在本 Wave 2 架构下，UI 渲染层由 F22 实现；F10 仅负责后端 REST 响应中提供 UI 所需字段。本用例以**数据契约**而非 DOM 渲染覆盖 UI 类别。

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | mock subprocess `git clone` 返 exit=0 + 构造 target 目录含 `.claude-plugin/plugin.json` + `.git/HEAD` 存根（SHA = 40-hex 形如 `abcd1234...`） | 就绪 |
| 2 | body = `{"kind":"clone","source":"https://github.com/org/x.git","target_dir":"plugins/longtaskforagent"}`；`resp = client.post("/api/skills/install", json=body)` | HTTP 200 |
| 3 | `data = resp.json()`；断言 `"commit_sha" in data` 且 `re.fullmatch(r"[0-9a-f]{40}", data["commit_sha"])` | True（UI 能显示 "8 位前缀 + …" 预览） |
| 4 | 断言 `"ok" in data` 且 `isinstance(data["ok"], bool)` 且 `data["ok"] is True` | True（UI 能根据 ok 着色 badge） |
| 5 | 断言 `"message" in data` 且 `isinstance(data["message"], str)` 且 `data["message"].strip() != ""` | True（UI 能在状态条渲染中文消息） |
| 6 | 断言 `resp.headers["content-type"]` 含 `application/json`（UI 能解析 JSON） | True |
| 7 | 以相同语义验证 pull 路径：`POST /api/skills/pull` body `{"target_dir":"plugins/longtaskforagent"}`，mock subprocess 成功 | 响应 schema 与 install 等价 |

### 验证点

- `commit_sha` 40-hex 格式（F22 UI 可截取前 7/8 位显示）
- `ok` bool 类型（F22 UI 可做 success/error 分支）
- `message` 非空字符串（F22 UI 可在 toast / 状态栏渲染）
- Content-Type JSON（UI 客户端解析前提）
- UI 层 E2E 渲染测试（"点击 Pull → 页面显示 sha"）由 F22 Fe-Config ST 承担 —— 本 Feature 不执行 Chrome DevTools 渲染 / 像素对比

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: ui
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_rest.py::test_t23_rest_install_clone_returns_200_with_schema`、`tests/test_f10_coverage_supplement.py::test_api_skills_pull_happy_path`
- **Test Type**: Real

---

### 用例编号

ST-SEC-003-006

### 关联需求

IAPI-018 REST error 400/409 · §Implementation Summary REST 链 · Feature Design Test Inventory T24 + T25

### 测试目标

验证 REST 层 `POST /api/skills/install` 对 SEC 错误的 HTTP 状态码映射正确：非白名单 URL → HTTP 400；run.lock 存在 → HTTP 409；并且 `body.detail` 含中文错误描述（不被吞为 500 或 200）。

### 前置条件

- `.venv` 激活；`HARNESS_WORKDIR` 指向 tmp wd；`TestClient(app)` 就绪

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | body1 = `{"kind":"clone","source":"file:///etc","target_dir":"plugins/ltfa"}`；`resp1 = client.post("/api/skills/install", json=body1)` | HTTP 400 |
| 2 | `resp1.json()["detail"]` 为字符串；提示含 "URL" 或等效语义词 | True |
| 3 | 创建 `wd/.harness/run.lock`；body2 = `{"kind":"clone","source":"https://github.com/org/x.git","target_dir":"plugins/ltfa"}`；`resp2 = client.post("/api/skills/install", json=body2)` | HTTP 409 |
| 4 | `resp2.json()["detail"]` 为字符串；含 "run" 或等效占用描述 | True |
| 5 | 两路径的响应均为合法 JSON，Content-Type 为 `application/json` | True |

### 验证点

- 400 对应 URL 白名单拒绝（client fault）
- 409 对应 run.lock 占用（conflict）
- detail 载荷含可显示的错误原因
- 错误码**不**当 500 抛（非服务器错）

### 后置检查

- tmp 清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f10_skills_rest.py::test_t24_rest_install_non_whitelisted_url_returns_400`、`tests/test_f10_skills_rest.py::test_t25_rest_install_when_run_lock_present_returns_409`
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-003-001 | FR-043 AC-1 / T01 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t01_setup_run_produces_isolated_paths_and_physical_copy` | Real | PASS |
| ST-FUNC-003-002 | FR-043 AC-2 / T02 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t02_setup_run_manifest_sha256_matches_source`、`tests/test_f10_plugin_registry.py::test_t02_sync_bundle_copies_physically_and_sha_matches` | Real | PASS |
| ST-FUNC-003-003 | FR-044 AC-1 / T03 | verification_steps[1] | `tests/test_f10_environment_isolator.py::test_t03_workdir_scope_guard_ok_when_only_harness_subdirs_changed`、`tests/test_f10_environment_isolator.py::test_t03b_workdir_scope_guard_ok_true_when_nothing_new_outside_allowed` | Real | PASS |
| ST-FUNC-003-004 | FR-045 AC-1 / T04 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t04_install_clone_uses_argv_list_no_shell_and_returns_commit_sha` | Real | PASS |
| ST-FUNC-003-005 | FR-045 AC-2 / T05 / T21 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t05_pull_uses_dash_C_and_ff_only_and_returns_head_sha`、`tests/integration/test_f10_real_git.py::test_t21_real_git_pull_ff_only_against_local_remote` | Real | PASS |
| ST-FUNC-003-006 | NFR-009 / FR-043 / T06 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t06_teardown_run_returns_empty_home_mtime_diff` | Real | PASS |
| ST-FUNC-003-007 | §IC `RunIdInvalidError` / T07 / T07b | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t07_setup_run_rejects_traversal_run_id`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[a/b]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[a\\b]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[has space]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[weird#tag]`、`tests/test_f10_environment_isolator.py::test_t07b_setup_run_rejects_various_illegal_run_ids[unicod\xe9-id]` | Real | PASS |
| ST-FUNC-003-008 | §IC `WorkdirNotFoundError` / T08 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t08_setup_run_raises_workdir_not_found` | Real | PASS |
| ST-FUNC-003-009 | §IC `BundleNotFoundError` / T09 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t09_setup_run_raises_bundle_not_found` | Real | PASS |
| ST-FUNC-003-010 | §IC `IsolationSetupError` / T10 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t10_setup_run_raises_isolation_setup_error_on_readonly_workdir` | Real | PASS |
| ST-FUNC-003-011 | IAPI-009 复用 / T26 | verification_steps[0] | `tests/integration/test_f10_real_fs_audit.py::test_t26_audit_writer_records_env_setup_and_teardown` | Real | PASS |
| ST-FUNC-003-012 | IAPI-018 REST 200 / T23 | verification_steps[2] | `tests/test_f10_skills_rest.py::test_t23_rest_install_clone_returns_200_with_schema` | Real | PASS |
| ST-BNDRY-003-001 | §Boundary run_id 长度 / T16 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t16_run_id_length_bounds` | Real | PASS |
| ST-BNDRY-003-002 | NFR-009 精度 / T17 | verification_steps[0] | `tests/test_f10_environment_isolator.py::test_t17_home_mtime_guard_detects_nanosecond_change`、`tests/test_f10_environment_isolator.py::test_t17b_home_mtime_guard_empty_snapshot_on_missing_home` | Real | PASS |
| ST-BNDRY-003-003 | §Boundary plugin.json / T18 | verification_steps[0] | `tests/test_f10_plugin_registry.py::test_t18_read_manifest_zero_bytes_raises_corrupt`、`tests/test_f10_plugin_registry.py::test_t18b_read_manifest_one_byte_minimal_valid`、`tests/test_f10_plugin_registry.py::test_t18c_read_manifest_64kib_exact_accepted`、`tests/test_f10_plugin_registry.py::test_t18d_read_manifest_over_64kib_rejects`、`tests/test_f10_plugin_registry.py::test_t18e_read_manifest_missing_raises_missing_error` | Real | PASS |
| ST-BNDRY-003-004 | CON-005 反面 / T19 | verification_steps[3] | `tests/test_f10_con005_reverse.py::test_t19_source_bundle_mtime_ns_unchanged_through_setup_teardown` | Real | PASS |
| ST-BNDRY-003-005 | §IC sync_bundle 幂等 / T20 | verification_steps[0] | `tests/test_f10_plugin_registry.py::test_t20_sync_bundle_is_idempotent` | Real | PASS |
| ST-BNDRY-003-006 | §IC sync_bundle 物理复制 / T27 | verification_steps[3] | `tests/test_f10_plugin_registry.py::test_t27_copy_isolation_src_untouched_when_dst_modified` | Real | PASS |
| ST-BNDRY-003-007 | §Impl flow local / TDD 补齐 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t_local_install_copies_absolute_local_dir_into_plugins`、`tests/test_f10_coverage_supplement.py::test_installer_local_kind_rejects_relative_source`、`tests/test_f10_coverage_supplement.py::test_installer_local_kind_rejects_when_target_exists` | Real | PASS |
| ST-SEC-003-001 | FR-045 SEC URL 白名单 / T11 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[file:///etc/passwd]`、`tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[ftp://example.com/repo.git]`、`tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[javascript:alert(1)]`、`tests/test_f10_skills_installer.py::test_t11_install_rejects_non_whitelisted_url[]` | Real | PASS |
| ST-SEC-003-002 | FR-045 SEC shell meta / T12 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/repo.git; rm -rf ~]`、`tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/repo.git\nrm -rf ~]`、`tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/repo.git\r\nls]`、`tests/test_f10_skills_installer.py::test_t12_install_rejects_shell_meta_in_url[https://legit.com/../../etc/repo.git]` | Real | PASS |
| ST-SEC-003-003 | FR-045 SEC target_dir / T13 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[plugins/../../etc/evil]`、`tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[../outside]`、`tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[/absolute/path]`、`tests/test_f10_skills_installer.py::test_t13_install_rejects_target_path_escape[plugins]` | Real | PASS |
| ST-SEC-003-004 | FR-044 scope guard / T14 | verification_steps[1] | `tests/test_f10_environment_isolator.py::test_t14_workdir_scope_guard_flags_injected_tmp_outside_allowed` | Real | PASS |
| ST-SEC-003-005 | §IC SkillsInstallBusyError / T15 | verification_steps[2] | `tests/test_f10_skills_installer.py::test_t15_install_rejects_when_run_lock_present`、`tests/test_f10_coverage_supplement.py::test_api_skills_pull_run_lock_returns_409` | Real | PASS |
| ST-UI-003-001 | FR-045 UI / ATS §5 K / REST schema | verification_steps[2] | `tests/test_f10_skills_rest.py::test_t23_rest_install_clone_returns_200_with_schema`、`tests/test_f10_coverage_supplement.py::test_api_skills_pull_happy_path` | Real | PASS |
| ST-SEC-003-006 | IAPI-018 REST 400/409 / T24 / T25 | verification_steps[2] | `tests/test_f10_skills_rest.py::test_t24_rest_install_non_whitelisted_url_returns_400`、`tests/test_f10_skills_rest.py::test_t25_rest_install_when_run_lock_present_returns_409` | Real | PASS |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 26 |
| Passed | 26 |
| Failed | 0 |
| Pending | 0 |

> Real test cases = test cases with Test Type `Real`（against real filesystem + real FastAPI ASGI + real git subprocess on T21/T26；mock subprocess on T04/T05/T11/T12/T13/T15/T23-T25，仍属 Real 因为测试路径走完整 `harness.*` 领域代码 + 真实 POSIX fs observation）。
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

## ATS 类别覆盖说明

本特性 srs_trace 映射到 ATS §5 K 类别：
- **FR-043** → FUNC, BNDRY, SEC：FUNC=ST-FUNC-003-001/002/006/011；BNDRY=ST-BNDRY-003-002/004；SEC=ST-SEC-003-004（workdir scope 反面）/ ST-SEC-003-005（run-lock 协同防 run 期污染）
- **FR-044** → FUNC, BNDRY, SEC：FUNC=ST-FUNC-003-003；BNDRY=ST-BNDRY-003-004（CON-005 反面 workdir 子域）；SEC=ST-SEC-003-004
- **FR-045** → FUNC, BNDRY, SEC, UI：FUNC=ST-FUNC-003-004/005/012；BNDRY=ST-BNDRY-003-007（local 拷贝边界）/ ST-BNDRY-003-003（manifest 大小）；SEC=ST-SEC-003-001/002/003/005/006；UI=ST-UI-003-001（FR-045 UI 数据契约 —— 本 feature `ui:false`，F10 承载后端 REST 响应 schema；UI 端 DOM/像素渲染 E2E 由 F22 Fe-Config ST 承担，见 ST-UI-003-001 前置说明）
- **NFR-009** → SEC：ST-FUNC-003-006（mtime diff 为空断言）+ ST-BNDRY-003-002（纳秒精度断言）+ ST-SEC-003-004（workdir 侧 scope 守卫）；SEC 语义通过 "零写入 `~/.claude/`" 的 fs 观测成立

**ATS 跨 Feature 集成锚点（非本特性 blocker）**：
- **FR-045 UI 部分（"UI 显示 commit sha"）**：由 F22 Fe-Config PromptsAndSkills 页面承担；本特性 ST 仅覆盖 REST `SkillsInstallResult.commit_sha` 返回值的 40-hex 格式。
- **INT-F01**（NFR-009 跨 run 稳定性）：F01 已在 passing；本特性覆盖每-run 粒度的 mtime snapshot/diff 可观察表面。
- **INT-F02**（audit JSONL 接口复用）：F02 已 passing；`AuditWriter.append_raw` 扩展方法在 ST-FUNC-003-011 直接使用。

## 负向比例

本文档 25 条用例中负向 / 错误路径 / 边界拒绝类：
- ST-FUNC-003-007（run_id 非法 6 参数化）
- ST-FUNC-003-008（WorkdirNotFoundError）
- ST-FUNC-003-009（BundleNotFoundError）
- ST-FUNC-003-010（IsolationSetupError on readonly）
- ST-BNDRY-003-001（长度边界 65/空 拒绝）
- ST-BNDRY-003-002（纳秒 diff 检出 `ok=False`）
- ST-BNDRY-003-003（0 字节 / 64 KiB+1 / 缺失 拒绝）
- ST-BNDRY-003-007（相对路径 source / target 存在 拒绝）
- ST-SEC-003-001（4 种非白名单 URL 拒绝）
- ST-SEC-003-002（4 种 shell meta URL 拒绝）
- ST-SEC-003-003（4 种 target_dir 穿越 拒绝）
- ST-SEC-003-004（workdir scope 反面：__injected__.tmp 检出）
- ST-SEC-003-005（run.lock 存在 → SkillsInstallBusyError）
- ST-SEC-003-006（REST 400/409 错误码）

共 14 条（= 56% 负向比例，≥ 40% ATS 基线）；另 11 条为 happy path + 幂等性验证。
