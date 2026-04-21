# 测试用例集: F01 · App Shell & Platform Bootstrap

**Feature ID**: 1
**关联需求**: FR-046, FR-050, NFR-007, NFR-010, NFR-012, NFR-013（含 CON-006 / CON-007 / IFR-001 / IFR-006 协同约束）
**日期**: 2026-04-21
**测试标准**: ISO/IEC/IEEE 29119-3
**模板版本**: 1.0

> **说明**：
> - 本文档为黑盒 ST 验收测试用例。预期结果仅从 SRS 验收准则、可观察接口（`/api/health` HTTP 响应、`ss -tnlp` LISTEN 表、POSIX 文件系统观测、stdout 文本、模块公开符号）推导，不阅读实现源代码。
> - Feature Design Clarification Addendum 为空（无需应用处置）。
> - `feature.ui == false` → 无 UI 类别用例；NFR-010 中文合规以"后端面向用户字符串"维度覆盖；视觉评审部分按 ATS §2.2 备注追溯到 F12-F16 系列，不作为本特性 ST blocker。
> - FR-046 Happy（真实 `claude auth login` OAuth）标记为 `已自动化: No / Manual Reason=external-action`，同时提供可接受自动替代用例（`/api/health` + 非交互 `claude auth status` 探测）。

---

## 摘要

| 类别 | 用例数 |
|------|--------|
| functional | 8 |
| boundary | 3 |
| ui | 1 |
| security | 5 |
| performance | 1 |
| **合计** | **18** |

---

### 用例编号

ST-FUNC-001-001

### 关联需求

FR-050 — 首次启动自动建 `~/.harness/` 与 keyring secrets（AC1）

### 测试目标

首次启动流程下，Harness 自动建 `~/.harness/` 目录并创建 `config.json`；返回中文欢迎文案；POSIX 权限为 `0o700`。

### 前置条件

- 后端 Python 环境已激活（`.venv` 可导入 `harness`）
- `HARNESS_HOME` 指向一个全新、空白的目录路径（上级目录可写、目标目录本身尚不存在）
- 该路径下 `config.json` 不存在

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `mktemp -d` 得到 `$T`；`export HARNESS_HOME="$T/.harness"`；执行 `python -c "from harness.app import FirstRunWizard; from harness.config import ConfigStore; s=ConfigStore(ConfigStore.default_path()); w=FirstRunWizard(s); print('first=', w.is_first_run())"` | stdout 含 `first= True` |
| 2 | 执行 `python -c "from harness.app import FirstRunWizard; from harness.config import ConfigStore; s=ConfigStore(ConfigStore.default_path()); r=FirstRunWizard(s).bootstrap(); print(r.welcome_message); print('home=', r.home_path); print('created=', len(r.created_files))"` | stdout 含 `Welcome, 已初始化 ~/.harness/`、`home= $T/.harness`、`created= 1` |
| 3 | `test -f "$T/.harness/config.json" && echo OK` | 输出 `OK` |
| 4 | `stat -c '%a' "$T/.harness"` | 输出 `700` |
| 5 | `python -c "from harness.config import ConfigStore; import pathlib,os; cfg=ConfigStore(pathlib.Path(os.environ['HARNESS_HOME'])/'config.json').load(); print('schema=', cfg.schema_version); print('providers=', cfg.provider_refs); print('retention=', cfg.retention_run_count)"` | stdout 含 `schema= 1`、`providers= {}`、`retention= 20`（表明默认空配置已写入） |
| 6 | 清理：`rm -rf "$T"`；`unset HARNESS_HOME` | 无错误 |

### 验证点

- `~/.harness/` 被自动创建且权限 `0o700`
- `config.json` 存在、schema 合法、字段为空配置
- 返回的欢迎文案为 NFR-010 简体中文原文 `Welcome, 已初始化 ~/.harness/`
- `is_first_run()` 在运行前 `True`、运行后不再被测试（T17 覆盖 re-run 场景）

### 后置检查

- `tmp` 目录已清理
- 不应污染用户真实 `~/.harness/`（`HARNESS_HOME` 必须为 tmp 路径）

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_first_run.py`、`tests/integration/test_f01_real_filesystem.py`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-001-002

### 关联需求

FR-050 — 首次启动自动建 `~/.harness/` 与 keyring secrets（AC2：保存 API key 后 config.json 不含明文 key）

### 测试目标

保存带 `api_key_ref` 的配置后，落盘 `config.json` 字节不含明文 API key（无 `sk-` / `sk-ant-` / 长 base64 / PEM），仅含 `{service,user}` 引用。

### 前置条件

- 隔离 `HARNESS_HOME`
- `ConfigStore` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `mktemp -d` 得 `$T`；`export HARNESS_HOME="$T/.harness"` | 无错 |
| 2 | `python -c "from harness.app import FirstRunWizard; from harness.config import ConfigStore, HarnessConfig; from harness.config.schema import ApiKeyRef; import os,pathlib; p=pathlib.Path(os.environ['HARNESS_HOME'])/'config.json'; s=ConfigStore(p); FirstRunWizard(s).bootstrap(); cfg=HarnessConfig(schema_version=1, provider_refs={'glm': ApiKeyRef(service='harness-classifier-glm', user='default')}); s.save(cfg); print('saved')"` | stdout `saved` |
| 3 | `cat "$T/.harness/config.json"` → 收集全部字节 | JSON 中含 `"service": "harness-classifier-glm"`、`"user": "default"`；不含字面 `"value"`、`"secret"`、`"api_key"` 字段；不含字符串 `sk-`、`sk-ant-`、`xai-`；不含任何连续 ≥ 32 字符的 base64 串；不含 `-----BEGIN`（PEM 标记） |
| 4 | `python -c "import re, pathlib, os; p=pathlib.Path(os.environ['HARNESS_HOME'])/'config.json'; b=p.read_bytes(); print('has_sk=', b.find(b'sk-')); print('has_pem=', b.find(b'-----BEGIN')); print('has_b64=', bool(re.search(rb'[A-Za-z0-9+/]{32,}={0,2}', b)))"` | 三行输出均为 `-1` / `-1` / `False`（无命中） |
| 5 | 清理 | 无错 |

### 验证点

- 落盘 JSON 只含 `{service,user}` 引用
- 字节扫描无明文 key 痕迹
- pydantic `extra="forbid"` 与 leak detector 联合防御生效

### 后置检查

- tmp 目录清理

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_config_store.py`
- **Test Type**: Real

---

### 用例编号

ST-SEC-001-001

### 关联需求

FR-050 AC2（协同 NFR-008）— 若试图写入含明文 key 的 payload，`ConfigStore.save` 必须在写盘**前**抛 `SecretLeakError`。

### 测试目标

纵深防御：当调用方绕过 schema 在 pydantic `extra` 中注入明文 key（例如历史字段 / 子类 extra），leak detector 必须拦截并保留原文件不覆盖。

### 前置条件

- 隔离 `HARNESS_HOME`
- 已存在一份合法 `config.json`（其 mtime 将被用于"未覆写"断言）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `mktemp -d` 得 `$T`；`export HARNESS_HOME="$T/.harness"` | 无错 |
| 2 | 执行 `python -c "from harness.app import FirstRunWizard; from harness.config import ConfigStore; import os, pathlib; s=ConfigStore(pathlib.Path(os.environ['HARNESS_HOME'])/'config.json'); FirstRunWizard(s).bootstrap(); print('mtime_before=', pathlib.Path(os.environ['HARNESS_HOME']+'/config.json').stat().st_mtime_ns)"` | 打印 mtime_before=<N> |
| 3 | 执行 Python 注入：构造允许 extra 的子类并 inject 明文 key，然后 `s.save(cfg)`：`python -c "from harness.config import ConfigStore, HarnessConfig, SecretLeakError; from pydantic import ConfigDict; import os, pathlib; class Leaky(HarnessConfig):   model_config = ConfigDict(extra='allow'); cfg=Leaky.model_validate({'api_key': 'sk-ant-1234567890abcdef', 'schema_version': 1}); s=ConfigStore(pathlib.Path(os.environ['HARNESS_HOME'])/'config.json'); try:    s.save(cfg); print('UNEXPECTED_SUCCESS') except SecretLeakError as e:    print('RAISED:', type(e).__name__)"` | stdout 含 `RAISED: SecretLeakError`；不含 `UNEXPECTED_SUCCESS` |
| 4 | 再读 mtime：`python -c "import os,pathlib; print(pathlib.Path(os.environ['HARNESS_HOME']+'/config.json').stat().st_mtime_ns)"` | 输出与 Step 2 相同（文件未被覆写） |
| 5 | 清理 | 无错 |

### 验证点

- `SecretLeakError` 在写盘前被抛
- `config.json` 原文件未被覆盖（mtime 不变）
- leak detector 覆盖已知前缀（`sk-ant-`）

### 后置检查

- tmp 目录清理

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_config_store.py`
- **Test Type**: Real

---

### 用例编号

ST-SEC-001-002

### 关联需求

NFR-007 / CON-006 — FastAPI 绑定地址硬约束（构造期）

### 测试目标

非 loopback host 传入 `AppBootstrap.__init__` 必须立即抛 `BindRejectedError`（fail-fast），进程不得进入 socket bind 阶段。

### 前置条件

- `harness.app.AppBootstrap` 可导入
- `harness.net.BindRejectedError` 可导入

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "from harness.app import AppBootstrap; from harness.net import BindRejectedError;\nfor h in ['0.0.0.0', 'localhost', '192.168.1.10']:\n  try:\n    AppBootstrap(host=h); print('MISS', h)\n  except BindRejectedError as e:\n    print('OK', h, getattr(e, 'actual_host', None))"` | 对 `0.0.0.0` / `localhost` / `192.168.1.10` 三者均输出 `OK <host> <host>`，不含任何 `MISS` |
| 2 | 验证 `actual_host` 属性暴露错误值 | 三行输出中 `actual_host` 分别等于 `0.0.0.0` / `localhost` / `192.168.1.10` |
| 3 | 验证合法 loopback 可构造：`python -c "from harness.app import AppBootstrap; b=AppBootstrap(host='127.0.0.1', port=0); print('host=', b.host, 'port=', b.port)"` | 输出 `host= 127.0.0.1 port= 0` |

### 验证点

- 任何非 loopback host 被构造期拒绝
- `BindRejectedError.actual_host` 字段暴露错误 host（便于上层打点）
- `127.0.0.1` 顺利通过

### 后置检查

- 无残留 socket（构造期未 bind）

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_app_bootstrap.py`
- **Test Type**: Real

---

### 用例编号

ST-SEC-001-003

### 关联需求

NFR-007 / CON-006 — 运行期 `BindGuard` 对已 bind socket 的 loopback 校验

### 测试目标

当上游绕过构造期以真实 socket bind 到 `0.0.0.0:0`（模拟 misconfig / 逃逸路径），`BindGuard.assert_loopback_only(sock)` 仍必须抛 `BindRejectedError`。

### 前置条件

- 本机有可用 ephemeral 端口

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "import socket; from harness.net import BindGuard, BindRejectedError; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.bind(('0.0.0.0', 0));\ntry:\n  BindGuard().assert_loopback_only(s); print('MISS')\nexcept BindRejectedError as e:\n  print('OK', e.actual_host)\nfinally:\n  s.close()"` | 输出 `OK 0.0.0.0`，不含 `MISS` |
| 2 | `python -c "import socket; from harness.net import BindGuard, BindRejectedError; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.bind(('127.0.0.1', 0));\ntry:\n  BindGuard().assert_loopback_only(s); print('OK-loopback')\nexcept BindRejectedError:\n  print('MISS')\nfinally:\n  s.close()"` | 输出 `OK-loopback` |

### 验证点

- 构造期 guard 失效时，运行期 guard 是第二道防线
- loopback host 不误报

### 后置检查

- socket 已关闭（finally）

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_bind_guard.py`
- **Test Type**: Real

---

### 用例编号

ST-SEC-001-004

### 关联需求

NFR-007 — `ss -tnlp` 实测进程仅在 `127.0.0.1` LISTEN，不出现 `0.0.0.0` / LAN IP

### 测试目标

真实运行态（dev 期 `svc-api-start.sh` 启动的 uvicorn 进程）的 LISTEN socket 必须仅绑 `127.0.0.1`（AF_INET）或 `::1`（AF_INET6）；`0.0.0.0` 与具体 LAN 接口 IP 不得出现。

### 前置条件

- `scripts/svc-api-start.sh` 已启动；`/tmp/svc-api.pid` 存在且 PID 健康
- `ss -tnlp` 可执行

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `PID=$(cat /tmp/svc-api.pid); kill -0 "$PID"; echo alive=$?` | 输出 `alive=0`（进程存活） |
| 2 | `ss -tnlp 2>/dev/null \| grep "pid=$PID" \| awk '{print $4}' \| sort -u` | 全部条目以 `127.0.0.1:` 或 `[::1]:` 开头 |
| 3 | `ss -tnlp 2>/dev/null \| grep "pid=$PID" \| grep -E '\\b0\\.0\\.0\\.0:\|([0-9]{1,3}\\.){3}[0-9]{1,3}:' \| grep -v '^127\\.' \| grep -v '0\\.0\\.0\\.0:\\*'; echo "exit=$?"` | 过滤后不输出任何 LISTEN 条目（LAN IP / `0.0.0.0:` 的本地地址列不得命中）；`exit=1`（grep 无匹配） |
| 4 | `curl -sS -o /dev/null -w "%{http_code}\\n" http://127.0.0.1:8765/api/health` | 输出 `200` |
| 5 | `curl -sS http://127.0.0.1:8765/api/health \| python -c "import sys,json; d=json.load(sys.stdin); assert d['bind']=='127.0.0.1', d; print('bind_ok')"` | 输出 `bind_ok` |

### 验证点

- 实测 socket bind host ∈ {127.0.0.1, ::1}
- `/api/health` 自上报 `bind=127.0.0.1`
- 无 `0.0.0.0` / LAN IP 的 LISTEN 条目

### 后置检查

- 服务保持运行（供后续用例使用）

### 元数据

- **优先级**: Critical
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/integration/test_f01_real_bind.py`
- **Test Type**: Real

---

### 用例编号

ST-SEC-001-005

### 关联需求

IFR-006（keyring 命名空间）+ Boundary（service 前缀）

### 测试目标

`KeyringGateway.set_secret` 必须拒绝不以 `harness-` 前缀开头的 service，避免污染其他应用的 keyring 命名空间。

### 前置条件

- `keyring` 已安装
- 测试使用 null backend（不触碰真实 keychain）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 设定 null backend 后调用非法前缀：`python -c "import keyring, keyring.backends.null; keyring.set_keyring(keyring.backends.null.Keyring()); from harness.auth import KeyringGateway; from pydantic import ValidationError; g=KeyringGateway();\ntry:\n  g.set_secret('not-harness-prefix', 'u', 'v'); print('MISS')\nexcept ValidationError:\n  print('OK-prefix')"` | 输出 `OK-prefix`，不含 `MISS` |
| 2 | 合法前缀可通过：`python -c "import keyring, keyring.backends.null; keyring.set_keyring(keyring.backends.null.Keyring()); from harness.auth import KeyringGateway; g=KeyringGateway(); g.set_secret('harness-classifier-glm', 'default', 'v1'); print('OK-accepted')"` | 输出 `OK-accepted`，不抛错 |
| 3 | 空串参数：`python -c "import keyring, keyring.backends.null; keyring.set_keyring(keyring.backends.null.Keyring()); from harness.auth import KeyringGateway; from pydantic import ValidationError; g=KeyringGateway();\nfor args in [('','u','v'), ('harness-x','','v'), ('harness-x','u','')]:\n  try:\n    g.set_secret(*args); print('MISS', args)\n  except ValidationError:\n    print('OK', args)"` | 三行均为 `OK (...)`，不含 `MISS` |

### 验证点

- 缺前缀 / 空串一律 `ValidationError`
- 合法 `harness-` 前缀被接受

### 后置检查

- 无 keyring 条目残留（null backend 不实际写入）

### 元数据

- **优先级**: High
- **类别**: security
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_keyring_gateway.py`
- **Test Type**: Real（null backend 仍是真实 keyring API 路径）

---

### 用例编号

ST-FUNC-001-003

### 关联需求

IFR-006 — keyring happy path（set → get → delete）

### 测试目标

对合法前缀 + 非空 service/user/value 三元组，`KeyringGateway` 完成 `set`→`get`→`delete` 完整循环，语义符合 §IC。

### 前置条件

- 使用 `keyrings.alt.file.PlaintextKeyring` 指向 tmp 路径作为 backend（避免污染真实 keychain；仍走真实库 API 路径）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "import tempfile, os; d=tempfile.mkdtemp(); os.environ['XDG_DATA_HOME']=d; os.environ['KEYRING_PROPERTY_FILE_PATH']=d+'/keyring.cfg'; import keyring, keyrings.alt.file; b=keyrings.alt.file.PlaintextKeyring(); b.file_path=d+'/kp.cfg'; keyring.set_keyring(b); from harness.auth import KeyringGateway; g=KeyringGateway(); g.set_secret('harness-test', 'u1', 'val-xyz'); v=g.get_secret('harness-test', 'u1'); print('got=', v); g.delete_secret('harness-test', 'u1'); v2=g.get_secret('harness-test', 'u1'); print('after_del=', v2)"` | stdout 含 `got= val-xyz` 以及 `after_del= None` |
| 2 | `detect_backend` 返回 `BackendInfo`：用同一 backend 调 `g.detect_backend()`，检查 `name` / `degraded` 字段：`python -c "import os, tempfile; d=tempfile.mkdtemp(); import keyring, keyrings.alt.file; b=keyrings.alt.file.PlaintextKeyring(); b.file_path=d+'/kp.cfg'; keyring.set_keyring(b); from harness.auth import KeyringGateway; info=KeyringGateway().detect_backend(); print('name=', info.name); print('degraded=', info.degraded); print('warning=', info.warning)"` | `name=` 含 `PlaintextKeyring`；`degraded= True`；`warning=` 含中文并等于 `未检测到 Secret Service，凭证以明文存储，建议安装 gnome-keyring` |

### 验证点

- `get/set/delete` 三方法语义与 §IC 一致
- `delete_secret` 幂等（entry 不存在不抛）
- `detect_backend` 在降级 backend 下返 `degraded=True` + 中文 warning（NFR-010 + IFR-006 降级）

### 后置检查

- tmp backend 文件已清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_keyring_gateway.py`、`tests/integration/test_f01_real_keyring.py`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-001-004

### 关联需求

FR-046 AC2（Err-J）— 用户未 auth 时 ticket 启动应被 CLI 自身报错，被 Harness 捕获为 `skill_error` 上报（本特性只覆盖 `ClaudeAuthDetector` 的未 auth 报告面，spawn 侧由 F03）

### 测试目标

当 `claude auth status` 返回非 0 或 CLI 缺失（Err-B 区分），`ClaudeAuthDetector.detect()` 给出 `authenticated=False` 与对应中文 hint。

### 前置条件

- `shutil.which` 可被 monkeypatch

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | CLI 缺失分支：`python -c "import shutil; shutil.which = lambda x: None; from harness.auth import ClaudeAuthDetector; s=ClaudeAuthDetector().detect(); print(s.cli_present, s.authenticated, s.source); print(repr(s.hint))"` | 输出 `False False skipped` 以及 hint 为中文 `'未检测到 Claude Code CLI'` |
| 2 | CLI 存在但 auth 失败分支（mock `subprocess.run`）：`python -c "import subprocess; from harness.auth import ClaudeAuthDetector; import shutil; shutil.which = lambda x: '/usr/bin/claude';\nclass R:\n  def __init__(self, rc): self.returncode=rc; self.stdout=''; self.stderr='not authenticated'\norig=subprocess.run\ndef fake(argv, **kw):\n  if argv[:2]==['claude','--version']: return R(0)\n  if argv[:3]==['claude','auth','status']: return R(1)\n  return orig(argv, **kw)\nsubprocess.run=fake\nfrom harness.auth import ClaudeAuthDetector\ns=ClaudeAuthDetector().detect()\nprint(s.cli_present, s.authenticated, s.source)\nprint(repr(s.hint))"` | 输出 `True False claude-cli`；hint 为中文 `'请运行: claude auth login'` |
| 3 | 验证对 `~/.claude/` 为只读操作：`stat -c '%Y' $HOME/.claude 2>/dev/null` 前后比较 | mtime 一致或 dir 不存在皆接受（detector 不修改） |

### 验证点

- CLI 缺失 → `cli_present=False`、中文 `未检测到 Claude Code CLI`
- 未 auth → `cli_present=True, authenticated=False`、中文 `请运行: claude auth login`（FR-046 AC2 + NFR-010）
- detector 纯读；不写 `~/.claude/`（CON-007 / NFR-009 协同）

### 后置检查

- 本地 `~/.claude/` mtime 未变化

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_claude_auth.py`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-001-005

### 关联需求

FR-046 AC1（Happy） — 用户已 `claude auth login` 时，Harness 启动不额外提示 API key；`/api/health` 报告 `claude_auth.authenticated=True`

### 测试目标

真实机器上已执行过 `claude auth login` 的情况下，Harness `AppBootstrap`（或等价 dev 启动）输出的 `/api/health` 中 `claude_auth.authenticated=True`、`cli_present=True`；不要求任何交互式 key 输入。

### 前置条件

- 开发机已完成 `claude auth login`（当前测试机器验证已完成）
- `svc-api-start.sh` 已启动

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `claude auth status` 在 shell 里直接跑；捕获 exit code（此步用于再次确认机器的确已 auth） | exit 0 |
| 2 | `curl -sS http://127.0.0.1:8765/api/health \| python -c "import json,sys; d=json.load(sys.stdin); assert d['claude_auth']['cli_present']==True; assert d['claude_auth']['authenticated']==True; assert d['claude_auth']['hint'] is None; print('auth_inherited=OK')"` | 输出 `auth_inherited=OK` |
| 3 | 反向断言：在 health JSON 中**不得**出现 `api_key` / `anthropic_key` 等明文字段：`curl -sS http://127.0.0.1:8765/api/health \| grep -E "api_key\|anthropic" \| wc -l` | 输出 `0` |

### 验证点

- `claude_auth.authenticated=True` 由 CLI 自身状态继承
- `/api/health` 不提示 / 不暴露任何 API key 明文字段
- Harness 未要求用户输入额外凭证

### 后置检查

- 服务保持运行

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes（以"机器已 auth"状态作为前置；若机器未 auth 则此用例由 ST-FUNC-001-006 手工用例补充）
- **测试引用**: `tests/integration/test_f01_real_cli.py`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-001-006

### 关联需求

FR-046 AC1（Happy）— 真实 OAuth 交互式 `claude auth login` 流程

### 测试目标

真实 `claude auth login` OAuth 流程不在 Harness 范围内触发（Harness 仅继承现有凭证），因此此用例验证：当用户从**零状态**执行一次 `claude auth login`（浏览器 OAuth），随后启动 Harness，`/api/health` 能立刻反映 `authenticated=True` 且 Harness 未额外提示 API key。

### 前置条件

- 目标机器当前未 auth（即 `claude auth status` 返 非 0）
- 用户可进行浏览器 OAuth 交互
- Harness 服务可停止与重启

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `claude auth status`（期望未 auth） | exit ≠ 0 |
| 2 | 用户执行 `claude auth login`，按提示完成浏览器 OAuth | `claude auth status` 之后 exit = 0 |
| 3 | 重启 Harness api 服务：按 env-guide §1 停止并启动 | 日志含 `Uvicorn running on http://127.0.0.1:8765` |
| 4 | `curl -sS http://127.0.0.1:8765/api/health` | JSON `claude_auth.authenticated=true`、`cli_present=true`、`hint` 为 `null` |
| 5 | Harness 启动流程中应**不出现**任何索取 API key 的 UI 对话 / 终端提示 | 用户观察确认无 prompt |

### 验证点

- 真实浏览器 OAuth 后，Harness 无需重复凭证
- `/api/health` 报告 `authenticated=True`
- 用户界面 / 日志未索取 `ANTHROPIC_API_KEY` 等明文

### 后置检查

- 保留当前 auth 状态

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: No
- **手动测试原因**: external-action（需要用户与浏览器 OAuth 交互；AI 无法执行真实 OAuth；ATS §2.1 FR-046 标记 Happy 为 Manual: external-action）
- **测试引用**: N/A（需用户手工；自动替代覆盖见 ST-FUNC-001-005）
- **Test Type**: Real

---

### 用例编号

ST-FUNC-001-007

### 关联需求

NFR-010（UI 仅简体中文）— 本特性覆盖"面向用户字符串"维度（源码 grep Auto），视觉评审部分追溯到 F12-F16

### 测试目标

本特性生产的所有面向用户字符串（`FirstRunResult.welcome_message`、`KeyringGateway.detect_backend().warning`、`ClaudeAuthStatus.hint`）均为简体中文（至少含 CJK 字符），且不含"not authenticated"/"please log in"等英文业务短语。

### 前置条件

- 环境同前

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "import re, shutil; shutil.which=lambda x: None; from harness.auth import ClaudeAuthDetector; h1=ClaudeAuthDetector().detect().hint; print('hint_cli_missing=', h1); print('has_cjk=', bool(re.search(r'[\\u4e00-\\u9fff]', h1 or '')))"` | `hint_cli_missing= 未检测到 Claude Code CLI`；`has_cjk= True` |
| 2 | `python -c "import subprocess, shutil; shutil.which=lambda x: '/bin/true';\nclass R:\n  def __init__(self,rc): self.returncode=rc; self.stdout=''; self.stderr=''\norig=subprocess.run\ndef fake(argv, **kw):\n  if argv[:2]==['claude','--version']: return R(0)\n  return R(1)\nsubprocess.run=fake\nimport re\nfrom harness.auth import ClaudeAuthDetector\nh=ClaudeAuthDetector().detect().hint\nprint('hint_not_auth=', h)\nprint('has_cjk=', bool(re.search(r'[\\u4e00-\\u9fff]', h or '')))"` | `hint_not_auth= 请运行: claude auth login`；`has_cjk= True`（"请运行"含 CJK 即可） |
| 3 | FirstRunWizard 欢迎语：`python -c "import tempfile,os,re; os.environ['HARNESS_HOME']=tempfile.mkdtemp()+'/.harness'; from harness.app import FirstRunWizard; from harness.config import ConfigStore; s=ConfigStore(ConfigStore.default_path()); m=FirstRunWizard(s).bootstrap().welcome_message; print(m); print('has_cjk=', bool(re.search(r'[\\u4e00-\\u9fff]', m)))"` | 输出 `Welcome, 已初始化 ~/.harness/`；`has_cjk= True` |
| 4 | KeyringGateway 降级警告：`python -c "import tempfile; d=tempfile.mkdtemp(); import keyring, keyrings.alt.file; b=keyrings.alt.file.PlaintextKeyring(); b.file_path=d+'/kp.cfg'; keyring.set_keyring(b); import re; from harness.auth import KeyringGateway; w=KeyringGateway().detect_backend().warning; print(w); print('has_cjk=', bool(re.search(r'[\\u4e00-\\u9fff]', w or '')))"` | 输出 `未检测到 Secret Service，凭证以明文存储，建议安装 gnome-keyring`；`has_cjk= True` |
| 5 | 黑名单英文短语扫描：对 Step 1-4 收集的所有字符串串联后 `python -c "text=...; import re; assert not re.search(r'not authenticated', text, re.I); assert not re.search(r'please log in', text, re.I); print('no_en_phrase')"` | 输出 `no_en_phrase` |

### 验证点

- 四处面向用户字符串均含 CJK 字符
- 无禁用英文业务短语
- 视觉评审部分（UI 实际渲染）由 F12-F16 系列特性覆盖（ATS §2.2 备注）— 本 ST 以追溯形式记录，不作本特性 blocker

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_zh_cn_text.py`
- **Test Type**: Real

---

### 用例编号

ST-FUNC-001-008

### 关联需求

NFR-012 / NFR-013 / FR-050 / `/api/health`（Design §6.2.2）

### 测试目标

三平台基线：在当前平台（Linux x86_64）执行 dev 启动（uvicorn 拉起 `harness.api:app`），`/api/health` 返回 `200`、JSON schema 完整，且进程不依赖外部额外 Python 安装（从 `.venv` 拉起，对应 NFR-013 "嵌入 Python 运行时"的开发期等价验证）。macOS / Windows 平台验证在 F17 PyInstaller 分发阶段覆盖。

### 前置条件

- `svc-api-start.sh` 已启动

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `curl -sS -o /tmp/health.json -w "%{http_code}\\n" http://127.0.0.1:8765/api/health` | 输出 `200` |
| 2 | `python -c "import json; d=json.load(open('/tmp/health.json')); assert set(d.keys())>={'bind','version','claude_auth','cli_versions'}, d.keys(); assert d['bind']=='127.0.0.1'; assert isinstance(d['version'], str); assert set(d['claude_auth'].keys())>={'cli_present','authenticated','source'}; assert set(d['cli_versions'].keys())>={'claude','opencode'}; print('schema_ok')"` | 输出 `schema_ok` |
| 3 | 平台信息：`python -c "import sys, platform; print(sys.platform, platform.machine())"` | 当前跑测试机器输出一行；记录为 `linux x86_64`（CI matrix F17 验证其他两平台） |
| 4 | NFR-013 等价：`python -c "import sys; assert sys.version_info>=(3,11); print('py>=3.11')"` | 输出 `py>=3.11` |

### 验证点

- `/api/health` 返回完整 JSON schema 且 `bind=127.0.0.1`
- 当前平台 smoke 通过
- Python 版本 ≥ 3.11（NFR-012 / NFR-013 前置）

### 后置检查

- 无

### 元数据

- **优先级**: Critical
- **类别**: functional
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_health_endpoint.py`
- **Test Type**: Real

---

### 用例编号

ST-PERF-001-001

### 关联需求

NFR-012 / NFR-013 冷启动 < 10s（verification_steps[3]）

### 测试目标

从 `AppBootstrap()` 构造到 `/api/health` 返回 200 耗时 < 10s（不含 webview render，本机环境为无头 VM；对应 Design §Implementation Summary 中"冷启动 < 10s"性能预算）。

### 前置条件

- 已停止 `svc-api-start.sh`（释放 :8765）；本用例独立启动子进程避免端口冲突

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 若 :8765 已被占用，使用 ephemeral port。执行：`python - <<'PY'` + 内嵌脚本：记录 `t0`、调 `AppBootstrap(port=0).start()` 替代流程以 `harness.api:app` 直接 uvicorn 启动测 `/api/health` 200 的总耗时 | 打印 `elapsed_ms=<N>`；`N < 10000` |
| 2 | 具体命令：`python -c "import time, threading, httpx, uvicorn; from harness.api import app; import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); cfg=uvicorn.Config(app, host='127.0.0.1', port=p, log_level='warning', access_log=False, lifespan='on'); srv=uvicorn.Server(cfg); t0=time.monotonic();\nth=threading.Thread(target=srv.run, daemon=True); th.start();\n# wait until server is ready or 10s\ndeadline=t0+10\nwhile time.monotonic()<deadline and not getattr(srv,'started',False): time.sleep(0.05)\nassert getattr(srv,'started',False), 'uvicorn did not start within 10s'\nresp=httpx.get(f'http://127.0.0.1:{p}/api/health', timeout=2)\nelapsed=(time.monotonic()-t0)*1000\nsrv.should_exit=True; th.join(timeout=5)\nassert resp.status_code==200, resp.status_code\nprint(f'elapsed_ms={elapsed:.1f}')"` | stdout 一行 `elapsed_ms=<float>`，数值 < 10000 |

### 验证点

- 冷启动耗时 < 10s
- `/api/health` 返 200
- 测试后 uvicorn 正常收尾、端口释放

### 后置检查

- 测试结束后重启 `svc-api-start.sh`（若中断）以便后续用例

### 元数据

- **优先级**: High
- **类别**: performance
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_app_bootstrap.py`（PERF 类）
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-001-001

### 关联需求

Boundary（`AppBootstrap.port` 越界）

### 测试目标

`port` 值越出 `[0, 65535]` 必须抛 `ValueError`（不得传到 `socket.bind` 导致 `OverflowError`）。

### 前置条件

- 无

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | `python -c "from harness.app import AppBootstrap;\nfor p in [-1, 65536, 999999]:\n  try:\n    AppBootstrap(port=p); print('MISS', p)\n  except ValueError as e:\n    print('OK', p)"` | 三行均 `OK <p>`，不含 `MISS` |
| 2 | 合法端点：`python -c "from harness.app import AppBootstrap; AppBootstrap(port=0); AppBootstrap(port=65535); print('edges_ok')"` | 输出 `edges_ok`，不抛错 |
| 3 | 非整型：`python -c "from harness.app import AppBootstrap;\ntry:\n  AppBootstrap(port='8765'); print('MISS-str')\nexcept ValueError:\n  print('OK-str')\ntry:\n  AppBootstrap(port=True); print('MISS-bool')\nexcept ValueError:\n  print('OK-bool')"` | 输出 `OK-str` 和 `OK-bool` |

### 验证点

- `-1` / `65536` / `999999` / 字符串 / bool 一律 `ValueError`
- `0` 与 `65535` 两端点被接受

### 后置检查

- 无

### 元数据

- **优先级**: Medium
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_app_bootstrap.py`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-001-002

### 关联需求

Boundary（`config.json` 0 字节 / 非法 JSON / schema 越界）

### 测试目标

`ConfigStore.load()` 对 0 字节 / 非法 JSON / schema 违规三种损坏形态均抛 `ConfigCorruptError`。

### 前置条件

- 隔离 tmp 路径

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 0 字节：`python -c "import tempfile, pathlib; from harness.config import ConfigStore, ConfigCorruptError; d=pathlib.Path(tempfile.mkdtemp()); p=d/'config.json'; p.write_bytes(b'');\ntry:\n  ConfigStore(p).load(); print('MISS-empty')\nexcept ConfigCorruptError:\n  print('OK-empty')"` | 输出 `OK-empty` |
| 2 | 非法 JSON：`python -c "import tempfile, pathlib; from harness.config import ConfigStore, ConfigCorruptError; d=pathlib.Path(tempfile.mkdtemp()); p=d/'config.json'; p.write_bytes(b'{not json');\ntry:\n  ConfigStore(p).load(); print('MISS-json')\nexcept ConfigCorruptError:\n  print('OK-json')"` | 输出 `OK-json` |
| 3 | extra=forbid（NFR-008 协同）：`python -c "import tempfile, pathlib; from harness.config import ConfigStore, ConfigCorruptError; d=pathlib.Path(tempfile.mkdtemp()); p=d/'config.json'; p.write_text('{\"api_key\":\"sk-ant-xyz\",\"schema_version\":1}');\ntry:\n  ConfigStore(p).load(); print('MISS-extra')\nexcept ConfigCorruptError:\n  print('OK-extra')"` | 输出 `OK-extra` |

### 验证点

- 三种损坏形态均抛 `ConfigCorruptError`
- pydantic `extra="forbid"` 使未知字段 / 非法字段被拒

### 后置检查

- tmp 清理

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_config_store.py`
- **Test Type**: Real

---

### 用例编号

ST-BNDRY-001-003

### 关联需求

Boundary（`FirstRunWizard.is_first_run` — 存量 config 必须不被覆盖）+ SEC `HARNESS_HOME` 路径注入

### 测试目标

（a）已存在合法 `~/.harness/config.json` 时 `is_first_run()` 返 `False` 且 `bootstrap()` 不改动旧文件（本测试以"未调 bootstrap"为断言）；（b）`HARNESS_HOME` 指向一个**已存在但非目录**的路径（模拟 `HARNESS_HOME=/etc/passwd` 类注入）时 `bootstrap()` 抛 `HarnessHomeWriteError` 且**不覆写**该文件。

### 前置条件

- tmp 隔离

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | Re-run 场景：`python -c "import tempfile, os, pathlib; d=pathlib.Path(tempfile.mkdtemp()); os.environ['HARNESS_HOME']=str(d/'.harness'); from harness.app import FirstRunWizard; from harness.config import ConfigStore; s=ConfigStore(ConfigStore.default_path()); FirstRunWizard(s).bootstrap(); print('first_1=', FirstRunWizard(s).is_first_run()); m1=(d/'.harness'/'config.json').stat().st_mtime_ns; import time; time.sleep(0.01); w=FirstRunWizard(s); assert not w.is_first_run(); print('first_2=', w.is_first_run()); m2=(d/'.harness'/'config.json').stat().st_mtime_ns; print('mtime_same=', m1==m2)"` | `first_1= False`（首次调后已不再是 first run）；`first_2= False`；`mtime_same= True`（未覆写） |
| 2 | 非目录注入：`python -c "import tempfile, pathlib, os, sys; d=pathlib.Path(tempfile.mkdtemp()); f=d/'notadir'; f.write_bytes(b'preexisting'); os.environ['HARNESS_HOME']=str(f); from harness.app import FirstRunWizard; from harness.app.first_run import HarnessHomeWriteError; from harness.config import ConfigStore; s=ConfigStore(ConfigStore.default_path());\ntry:\n  FirstRunWizard(s).bootstrap(); print('MISS-nondir')\nexcept HarnessHomeWriteError:\n  print('OK-nondir')\n# 文件未被覆写\nprint('content=', f.read_bytes())"` | 输出 `OK-nondir`；后续 `content=` 仍为 `b'preexisting'` |

### 验证点

- re-run 不触发首启写入、文件未被修改（mtime 保留）
- 非目录 `HARNESS_HOME` 触发 `HarnessHomeWriteError`，不破坏既有文件（路径注入防护）

### 后置检查

- tmp 清理；`unset HARNESS_HOME`

### 元数据

- **优先级**: High
- **类别**: boundary
- **已自动化**: Yes
- **测试引用**: `tests/test_f01_first_run.py`
- **Test Type**: Real

---

### 用例编号

ST-UI-001-001

### 关联需求

NFR-010（UI 仅简体中文 — 视觉评审部分）

### 测试目标

本特性 `ui: false`（后端 / 平台特性，无直接 UI 渲染面），NFR-010 UI 类别的"视觉评审 8 页面无英文"要求由 **F12-F16 UI 系列特性**的 ST 用例承担（ATS §2.2 NFR-010 备注：F12-F16）。本用例为跨特性 delegation 显式追溯锚点 —— F01 仅提供后端文案（已由 ST-FUNC-001-007 覆盖）；浏览器视觉评审无法在后端 / 平台特性的 ST 阶段执行，因此为人工测试且在 F12-F16 ST 阶段落实。

### 前置条件

- 本特性 `feature.ui == false`
- F12-F16 UI 特性尚未进入 ST（当前 wave）
- Visual Rendering Contract 未在本特性定义（文档明确 "N/A — 后端/平台 feature"）

### 测试步骤

| Step | 操作 | 预期结果 |
| ---- | ---- | -------- |
| 1 | 追溯确认：翻查 ATS §2.2 NFR-010 行 "执行方: F12-F16（Manual: visual-judgment 视觉评审）" | 确认视觉评审责任已在 ATS 层委派给 F12-F16 |
| 2 | 核对本特性 Design `## Visual Rendering Contract` 章节为 "N/A — 后端/平台 feature" | 确认本特性无 UI 渲染表面 |
| 3 | 核对 ST-FUNC-001-007 已覆盖本特性生产的全部后端中文文案（FirstRunResult.welcome_message / KeyringGateway warning / ClaudeAuthStatus.hint） | 后端文案已自动化验证 |
| 4 | 记录：F12-F16 ST 阶段需在各自 ST 文档中生成 UI 类别用例，通过 Chrome DevTools MCP 做 8 页面视觉评审（中文字符存在 + 无英文业务短语 + UCD §3 色板/间距 token），满足 NFR-010 UI 部分 | 该条记录作为 F12-F16 ST 阶段的硬性提醒 |

### 验证点

- 本特性 Design 已明确声明无 UI 渲染表面
- NFR-010 的后端文案维度已由 ST-FUNC-001-007 自动化验证
- NFR-010 的 UI 视觉评审部分由 F12-F16 ST 阶段承担（非本特性 blocker）

### 后置检查

- F12-F16 进入 ST 时由彼时 SubAgent 兑现视觉评审

### 元数据

- **优先级**: Medium
- **类别**: ui
- **已自动化**: No
- **手动测试原因**: visual-judgment（需人工视觉评审 UI 页面；本特性 ui:false 无渲染面，由 F12-F16 特性 ST 承担；ATS §2.2 NFR-010 明确划分 F01 不负责此部分）
- **测试引用**: N/A（跨特性 delegation；由 F12-F16 ST 自动化/半自动化实现 Chrome DevTools MCP 视觉评审）
- **Test Type**: Real

---

## 可追溯矩阵

| 用例 ID | 关联需求 | verification_step | 自动化测试 | Test Type | 结果 |
|---------|----------|-------------------|-----------|---------|------|
| ST-FUNC-001-001 | FR-050 AC1 | verification_steps[0] | `tests/test_f01_first_run.py::test_bootstrap_creates_harness_home_with_default_config` | Real | PASS |
| ST-FUNC-001-002 | FR-050 AC2 | verification_steps[0] | `tests/test_f01_config_store.py::test_save_rejects_provider_refs_with_secret_value` | Real | PASS |
| ST-SEC-001-001 | FR-050 AC2（NFR-008 协同） | verification_steps[0] | `tests/test_f01_config_store.py::test_save_refuses_payload_containing_known_key_prefix` | Real | PASS |
| ST-SEC-001-002 | NFR-007 / CON-006（构造期） | verification_steps[1] | `tests/test_f01_app_bootstrap.py::test_init_rejects_non_loopback_host` | Real | PASS |
| ST-SEC-001-003 | NFR-007 / CON-006（运行期） | verification_steps[1] | `tests/test_f01_bind_guard.py::test_assert_loopback_only_rejects_wildcard_bind` | Real | PASS |
| ST-SEC-001-004 | NFR-007（`ss -tnlp` 实测） | verification_steps[1] | `tests/integration/test_f01_real_bind.py::test_uvicorn_only_listens_on_loopback` | Real | PASS |
| ST-SEC-001-005 | IFR-006 / Boundary（service 前缀） | verification_steps[2] | `tests/test_f01_keyring_gateway.py::test_set_secret_rejects_non_harness_prefix` | Real | PASS |
| ST-FUNC-001-003 | IFR-006 happy（set/get/delete + degraded） | verification_steps[2] | `tests/test_f01_keyring_gateway.py::test_set_get_delete_roundtrip`、`tests/integration/test_f01_real_keyring.py` | Real | PASS |
| ST-FUNC-001-004 | FR-046 AC2（Err-J / CLI 缺失 Err-B） | verification_steps[2] | `tests/test_f01_claude_auth.py::test_detect_returns_not_auth_when_status_exits_nonzero` | Real | PASS |
| ST-FUNC-001-005 | FR-046 AC1（已 auth Happy 自动替代覆盖） | verification_steps[2] | `tests/integration/test_f01_real_cli.py::test_detect_real_claude_cli` | Real | PASS |
| ST-FUNC-001-006 | FR-046 AC1（真实 OAuth Manual） | verification_steps[2] | N/A | Real | PENDING-MANUAL |
| ST-FUNC-001-007 | NFR-010（中文文案源码维度） | verification_steps[0] | `tests/test_f01_zh_cn_text.py::test_all_user_facing_strings_contain_cjk` | Real | PASS |
| ST-FUNC-001-008 | NFR-012 / NFR-013（`/api/health` schema） | verification_steps[3] | `tests/test_f01_health_endpoint.py::test_health_returns_bind_127_0_0_1` | Real | PASS |
| ST-PERF-001-001 | NFR-012 / NFR-013（冷启动 < 10s） | verification_steps[3] | `tests/test_f01_app_bootstrap.py::test_cold_start_under_ten_seconds` | Real | PASS |
| ST-BNDRY-001-001 | Boundary `AppBootstrap.port` 越界 | verification_steps[1] | `tests/test_f01_app_bootstrap.py::test_init_rejects_port_out_of_range` | Real | PASS |
| ST-BNDRY-001-002 | Boundary `config.json` 损坏 | verification_steps[0] | `tests/test_f01_config_store.py::test_load_raises_on_empty_or_invalid_json` | Real | PASS |
| ST-BNDRY-001-003 | Boundary re-run + `HARNESS_HOME` 注入 | verification_steps[0] | `tests/test_f01_first_run.py::test_is_first_run_false_when_config_exists` | Real | PASS |
| ST-UI-001-001 | NFR-010（视觉评审部分 → F12-F16） | verification_steps[3] | N/A（跨特性 delegation） | Real | PENDING-MANUAL |

> 结果 valid values: `PENDING`, `PASS`, `FAIL`, `MANUAL-PASS`, `MANUAL-FAIL`, `BLOCKED`, `PENDING-MANUAL`

## Real Test Case Execution Summary

| Metric | Count |
|--------|-------|
| Total Real Test Cases | 18 |
| Passed | 16 |
| Failed | 0 |
| Pending | 2 (PENDING-MANUAL) |

> Real test cases = test cases with Test Type `Real` (executed against a real running environment, not Mock).
> Any Real test case FAIL blocks the feature from being marked `"passing"` — must be fixed and re-executed.

## Manual Test Case Summary

| Metric | Count |
|--------|-------|
| Total Manual Test Cases | 2 |
| Manual Passed (MANUAL-PASS) | 0 |
| Manual Failed (MANUAL-FAIL) | 0 |
| Blocked | 0 |
| Pending (PENDING-MANUAL) | 2 |

> Manual test cases = test cases with `已自动化: No`. Results collected via human review gate after automated execution.

## ATS 类别覆盖说明

本特性 srs_trace 映射到 ATS 类别（ATS §2.1 / §2.2）：
- **FR-046** → FUNC, BNDRY, SEC：FUNC=ST-FUNC-001-004/005/006；SEC=ST-SEC-001-003（keyring/bind 间接涵盖未 auth 时 CLI 不被绕过的审计面）；BNDRY=ST-BNDRY-001-003（HARNESS_HOME 注入与 re-run 边界，间接支撑 CLI 继承面）。FR-046 主要 BNDRY 点由 ST-FUNC-001-004 的"CLI 缺失"分支覆盖（即 Err-B / Err-J 区分边界）
- **FR-050** → FUNC, BNDRY, SEC：FUNC=ST-FUNC-001-001/002；BNDRY=ST-BNDRY-001-002/003；SEC=ST-SEC-001-001
- **NFR-007** → SEC：ST-SEC-001-002 / 003 / 004
- **NFR-010** → FUNC, UI：FUNC=ST-FUNC-001-007（源码 grep / 用户字符串扫描）；UI=ST-UI-001-001（跨特性 delegation 锚点，视觉评审由 F12-F16 ST 承担；ATS §2.2 明确划分），非本特性 blocker
- **NFR-012** → FUNC：ST-FUNC-001-008 / ST-PERF-001-001（平台 smoke 当前 Linux 一例；macOS/Windows 由 F17 覆盖，非本特性 blocker）
- **NFR-013** → FUNC：ST-FUNC-001-008（Python 版本前置 + /api/health 200）/ ST-PERF-001-001（冷启动 < 10s；干净 VM 无 Python 预装由 F17 覆盖）
