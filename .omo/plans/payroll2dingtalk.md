# Payroll2DingTalk - 工资单推送钉钉OA审批

## TL;DR

> **Quick Summary**: 构建Python/Streamlit Web应用，读取多个Excel工资表文件，提取每个甲方单位的汇总数据（转账合计、扣款合计、实发合计、个人所得税及其他），上传文件到钉钉空间，通过钉钉OA审批API创建审批实例。
> 
> **Deliverables**:
> - Excel解析模块（支持多种格式，基于列名匹配）
> - 钉钉API模块（Token管理、文件上传、审批创建、用户查询）
> - 用户认证模块（手机号登录→钉钉userId）
> - Streamlit Web UI（文件上传、数据预览、审批提交）
> - API验证脚本（验证关键假设）
> - TDD测试套件（pytest）
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 0 (API验证) → Task 2 (钉钉API模块) → Task 5 (Streamlit UI) → Task 6 (审批提交) → Task 7 (错误处理) → Task 8 (集成测试) → F1-F4

---

## Context

### Original Request
从业务系统获取工资单数据Excel表格 → 通过钉钉OA接口推送到钉钉发起审批流程

### Interview Summary
**Key Discussions**:
- 一个OA审批单由多份工资表组成（多个甲方单位）
- 标题格式："XX、XX等X家单位XXXX年XX月工资发放请示"
- 不同甲方Excel格式不同，但合计列名一致（转账合计、扣款合计、实发合计）
- 个人所得税及其他 = 转账合计 - 扣款合计 - 实发合计（DingTalk自动计算）
- 用户通过手机号登录，手机号与钉钉手机号一致
- 审批人已在模板中预设，无需API指定
- 技术栈：Python + Streamlit + TDD

**Research Findings**:
- 钉钉审批模板完整字段ID已从approval_cache.json获取
- PaySignPrinter项目提供了Token管理和API调用模式参考
- **文件上传必须用 Storage v1.0 API**（v2.0报500，Drive API权限不存在，/media/upload是临时文件不能用）
- 文件上传三步：获取uploadInfo → PUT上传到OSS(Content-Type必须为空) → Commit → fileId
- 创建审批**必须传deptId**参数（官方文档标非必填但实际必填，否则报sysErrror）
- TableField创建时也使用读取格式（rowValue + key），不需要details/rowValues
- 获取unionId必须用旧版oapi `/topapi/v2/user/get`（新版Contact API受可见范围限制）
- 钉钉API支持手机号查询用户ID (/topapi/v2/user/getbymobile)
- **完整API验证已通过**: 附件可在钉钉客户端正常打开 ✅

### Metis Review
**Identified Gaps** (addressed):
- API验证先行：文件上传和审批创建格式需要先测试验证 → 增加Task 0 API验证脚本
- CalculateField可能不会自动计算 → 验证脚本测试，如有问题则显式传值
- TableField创建格式需验证 → 验证脚本测试
- 手机号→userId API需确认 → 验证脚本测试
- 年月/单位名称提取逻辑需明确 → 从Excel标题行C1提取

---

## Work Objectives

### Core Objective
构建一个Python/Streamlit Web应用，解析多个Excel工资表，提取汇总数据，上传文件到钉钉空间，创建钉钉OA审批实例。

### Concrete Deliverables
- `/home/ubuntu/coding/Payroll2DingTalk/` 完整项目
- `excel_parser.py` - Excel解析模块（支持多格式）
- `dingtalk_api.py` - 钉钉API模块（Token、上传、审批、用户查询）
- `auth.py` - 用户认证模块
- `app.py` - Streamlit主界面
- `config.py` - 配置管理
- `tests/` - TDD测试套件
- `verify_api.py` - API验证脚本
- `.env` / `.env.example` - 环境变量

### Definition of Done
- [ ] 上传Excel文件后能正确解析汇总数据
- [ ] 能成功创建钉钉OA审批实例
- [ ] 审批中附件可正常查看/下载
- [ ] 审批中TableField数据正确显示
- [ ] 不同格式Excel均能正确解析
- [ ] 手机号登录正常工作
- [ ] 所有pytest测试通过

### Must Have
- 多Excel文件上传和解析
- 灵活的列名匹配解析（转账合计、扣款合计、实发合计）
- "合计"行自动定位
- 钉钉文件上传（spaceId: 2256226585）
- 钉钉审批创建（完整formComponentValues）
- 手机号登录→userId查询
- 提交前数据预览和确认
- TDD测试覆盖核心模块

### Must NOT Have (Guardrails)
- 不实现审批读取/下载功能（属于PaySignPrinter）
- 不实现签名插入/打印功能
- 不实现审批状态跟踪/通知
- 不使用数据库持久化
- 不添加Pydantic模型/dataclass/验证框架（使用普通dict和if/else）
- 不实现复杂重试逻辑（仅token刷新）
- 不复制PaySignPrinter的READ-only代码
- 不添加过度注释或JSDoc风格文档
- 不创建抽象基类（YAGNI）
- 不跨月批量创建审批

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (greenfield)
- **Automated tests**: YES (TDD)
- **Framework**: pytest
- **TDD flow**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Excel Parser**: Use Bash (python -c) - Import module, parse test file, assert values
- **DingTalk API**: Use Bash (python verify_api.py) - Call API, assert response fields
- **Streamlit UI**: Use Playwright - Navigate, upload files, verify preview, submit
- **Integration**: Use Playwright + Bash - Full flow from upload to approval creation

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (Start Immediately - API verification, MUST complete first):
└── Task 0: API验证脚本 [deep]

Wave 1 (After Task 0 - foundation + core modules, MAX PARALLEL):
├── Task 1: 项目脚手架 + 配置 [quick]
├── Task 2: 钉钉API模块 [deep]
├── Task 3: Excel解析模块 [deep]
├── Task 4: 用户认证模块 [quick]

Wave 2 (After Wave 1 - Streamlit UI):
├── Task 5: Streamlit主界面 + 文件上传 + 预览 [visual-engineering]
├── Task 6: 审批提交集成 [unspecified-high]

Wave 3 (After Wave 2 - integration + polish):
├── Task 7: 错误处理 + 边界情况 [quick]
├── Task 8: 集成测试 + 文档 [writing]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high + playwright)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 0 → Task 2 → Task 5 → Task 6 → Task 7 → Task 8 → F1-F4
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 0 | - | 2 | 0 |
| 1 | - | 5, 6 | 1 |
| 2 | 0 | 5, 6 | 1 |
| 3 | - | 5, 6 | 1 |
| 4 | - | 5, 6 | 1 |
| 5 | 1, 2, 3, 4 | 6 | 2 |
| 6 | 2, 3, 4, 5 | 7, 8 | 2 |
| 7 | 6 | 8 | 3 |
| 8 | 7 | F1-F4 | 3 |
| F1-F4 | 8 | - | FINAL |

### Agent Dispatch Summary

- **Wave 0**: 1 - T0 → `deep`
- **Wave 1**: 4 - T1 → `quick`, T2 → `deep`, T3 → `deep`, T4 → `quick`
- **Wave 2**: 2 - T5 → `visual-engineering`, T6 → `unspecified-high`
- **Wave 3**: 2 - T7 → `quick`, T8 → `writing`
- **FINAL**: 4 - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [ ] 0. API验证脚本 - 验证关键钉钉API假设

  **What to do**:
  - 创建 `verify_api.py` 独立脚本
  - 验证1: 获取AccessToken (POST /v1.0/oauth2/accessToken)
  - 验证2: 手机号查询userId (POST /topapi/v2/user/getbymobile)
  - 验证3: 获取审批表单Schema (GET /v1.0/workflow/forms/schemas/processCodes?processCode=PROC-xxx)
  - 验证4: 获取审批钉盘空间信息 (POST /v1.0/workflow/processInstances/spaces/infos/query)
  - 验证5: 上传文件到钉盘 (POST /v1.0/drive/spaces/{spaceId}/files/0/uploadInfos → PUT uploadUrl)
  - 验证6: 创建审批实例 (POST /v1.0/workflow/processInstances)，使用最少数据测试TableField格式
  - 验证7: CalculateField是否自动计算（测试提交含3个MoneyField和1个CalculateField的TableField行）
  - 每个验证步骤输出明确的PASS/FAIL结果
  - 从 `/home/ubuntu/coding/PaySignPrinter/.env` 读取凭证
  - 使用 `requests` 库，不使用SDK
  - 完整接口文档参考: `.omo/drafts/dingtalk-api-reference.md`

  **Must NOT do**:
  - 不使用alibabacloud_dingtalk SDK（太重，requests足够）
  - 不创建任何类或抽象
  - 不做错误恢复

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要研究不确定的API格式，调试可能的问题
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: 不涉及UI

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 0 (sequential, must complete first)
  - **Blocks**: Task 2
  - **Blocked By**: None

  **References**:

  **Pattern References** (existing code to follow):
  - `/home/ubuntu/coding/PaySignPrinter/dingtalk_api.py:1-60` - Token获取模式、requests调用模式、错误处理
  - `/home/ubuntu/coding/PaySignPrinter/.env` - 凭证格式 (DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, DINGTALK_PROCESS_CODE)

  **API/Type References** (contracts to implement against):
  - 钉钉AccessToken API: `POST https://api.dingtalk.com/v1.0/oauth2/accessToken` - Body: {"appKey":"...", "appSecret":"..."}
  - 手机号查询用户: `POST https://oapi.dingtalk.com/topapi/v2/user/getbymobile` - Body: {"mobile":"手机号"}
  - 文件上传: `POST https://api.dingtalk.com/v1.0/drive/spaces/2256226585/files/0/uploadInfos` - Body: {"fileName":"test.xlsx","fileSize":1234}
  - 创建审批: `POST https://api.dingtalk.com/v1.0/workflow/processInstances` - Header: x-acs-dingtalk-access-token

  **Test References** (testing patterns to follow):
  - 无（这是验证脚本，不是测试套件）

  **External References**:
  - DingTalk API docs: https://open.dingtalk.com/document/development/create-an-approval-instance

  **WHY Each Reference Matters**:
  - PaySignPrinter的dingtalk_api.py提供了Token获取和API调用的成熟模式，避免重复造轮子
  - .env文件有实际凭证，可直接用于测试
  - API端点是创建审批的核心，格式必须验证正确

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: API验证脚本全部通过
    Tool: Bash (python)
    Preconditions: .env文件存在且有有效凭证
    Steps:
      1. python verify_api.py
      2. 检查输出中每个验证步骤是否为PASS
    Expected Result: 7个验证步骤全部PASS (Token获取、用户查询、表单Schema、钉盘空间、文件上传、审批创建、CalculateField自动计算)
    Failure Indicators: 任何步骤输出FAIL
    Evidence: .omo/evidence/task-0-api-verify.txt

  Scenario: 文件上传验证
    Tool: Bash (python)
    Preconditions: AccessToken获取成功
    Steps:
      1. 上传测试Excel文件到钉钉空间spaceId=2256226585
      2. 验证返回的fileId非空
      3. 验证返回的uploadUrl可PUT成功
    Expected Result: fileId非空，HTTP 200返回
    Failure Indicators: fileId为空或PUT返回非200
    Evidence: .omo/evidence/task-0-file-upload.txt
  ```

  **Commit**: YES
  - Message: `feat(api): add DingTalk API verification script`
  - Files: `verify_api.py`
  - Pre-commit: `python verify_api.py`

- [ ] 1. 项目脚手架 + 配置

  **What to do**:
  - 创建 `requirements.txt`: streamlit, requests, python-dotenv, openpyxl, pytest
  - 创建 `.env.example`: DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_AGENT_ID, DINGTALK_PROCESS_CODE, DINGTALK_SPACE_ID=2256226585
  - 复制PaySignPrinter的.env到项目根目录
  - 创建 `config.py`: load_dotenv + 环境变量读取函数
  - 创建 `tests/` 目录和 `tests/conftest.py` (pytest配置)
  - 创建 `.gitignore`
  - 运行 `pip install -r requirements.txt` 确认依赖安装成功
  - 运行 `pytest` 确认测试框架正常工作

  **Must NOT do**:
  - 不创建Pydantic模型
  - 不创建数据类
  - 不添加过度配置（只做必要的）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准项目初始化，步骤明确
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5, 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/requirements.txt` - 依赖格式参考
  - `/home/ubuntu/coding/PaySignPrinter/.env.example` - 环境变量模板格式
  - `/home/ubuntu/coding/PaySignPrinter/.gitignore` - git忽略规则

  **API/Type References**:
  - `/home/ubuntu/coding/PaySignPrinter/dingtalk_api.py:load_env()` - 环境变量加载模式

  **WHY Each Reference Matters**:
  - PaySignPrinter的项目结构提供了成熟的项目配置模式

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test file created: tests/test_config.py
  - [ ] pytest tests/test_config.py → PASS

  **QA Scenarios:**

  ```
  Scenario: 依赖安装成功
    Tool: Bash
    Steps:
      1. pip install -r requirements.txt
      2. python -c "import streamlit; import requests; import openpyxl; import dotenv; import pytest; print('OK')"
    Expected Result: 输出 "OK"
    Failure Indicators: ImportError
    Evidence: .omo/evidence/task-1-deps-install.txt

  Scenario: 配置加载正常
    Tool: Bash (python)
    Steps:
      1. python -c "from config import get_config; c=get_config(); print(c['app_key'])"
    Expected Result: 输出DINGTALK_APP_KEY值
    Failure Indicators: KeyError或ImportError
    Evidence: .omo/evidence/task-1-config-load.txt
  ```

  **Commit**: YES
  - Message: `feat(scaffold): project setup with dependencies and config`
  - Files: `requirements.txt, .env.example, .env, config.py, tests/conftest.py, .gitignore`
  - Pre-commit: `pytest tests/ -v`

- [ ] 2. 钉钉API模块 (dingtalk_api.py)

  **What to do**:
  - TDD: 先写测试 `tests/test_dingtalk_api.py`
  - 实现 `dingtalk_api.py`，包含以下函数：
    - `get_access_token()` - 获取并缓存AccessToken（7000s刷新，参考PaySignPrinter模式）
    - `get_user_by_mobile(mobile)` - 手机号查询钉钉userId (POST /topapi/v2/user/getbymobile)
    - `get_form_schema(process_code)` - 获取审批表单Schema (GET /v1.0/workflow/forms/schemas/processCodes)
    - `get_attachment_space(agent_id=None, user_id=None)` - 获取审批钉盘空间信息 (POST /v1.0/workflow/processInstances/spaces/infos/query)
    - `upload_file_to_space(file_path, space_id, parent_id="0")` - 上传文件到钉盘空间，返回fileId
    - `create_approval_instance(process_code, originator_user_id, form_component_values, dept_id=-1)` - 创建审批实例
  - 每个函数使用 `requests` 库，timeout=30
  - 错误处理：检查response.status_code和response.json()中的错误码
  - Token缓存：使用模块级变量，记录过期时间

  **Must NOT do**:
  - 不使用alibabacloud_dingtalk SDK
  - 不复制PaySignPrinter的READ-only函数
  - 不添加过度抽象
  - 不实现审批查询/下载功能

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 钉钉API调用需要处理多种边界情况，Token管理、文件上传流程较复杂
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 5, 6
  - **Blocked By**: Task 0 (需要API验证结果确认格式)

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/dingtalk_api.py:1-100` - Token管理、API调用、错误处理模式
  - `/home/ubuntu/coding/PaySignPrinter/dingtalk_api.py:get_access_token()` - Token缓存和刷新逻辑

  **API/Type References**:
  - AccessToken: `POST https://api.dingtalk.com/v1.0/oauth2/accessToken` - Body: {"appKey":"...", "appSecret":"..."} → {"accessToken":"...", "expireIn":7200}
  - 手机号查用户: `POST https://oapi.dingtalk.com/topapi/v2/user/getbymobile` - Body: {"mobile":"..."} → {"result":{"userid":"..."}}
  - 文件上传Step1: `POST https://api.dingtalk.com/v1.0/drive/spaces/{spaceId}/files/{parentId}/uploadInfos` - Header: x-acs-dingtalk-access-token, Body: {"fileName":"...","fileSize":N} → {"uploadUrl":"...", "fileId":"...", "spaceId":N}
  - 文件上传Step2: `PUT {uploadUrl}` - Body: binary file data → 200 OK
  - 创建审批: `POST https://api.dingtalk.com/v1.0/workflow/processInstances` - Header: x-acs-dingtalk-access-token, Body见下方

  **创建审批请求体**:
  ```json
  {
    "processCode": "YOUR_PROCESS_CODE",
    "originatorUserId": "xxx",
    "deptId": -1,
    "formComponentValues": [
      {"name": "标题", "value": "XX等X家单位XXXX年XX月工资发放请示"},
      {"name": "批量上传工资单", "componentType": "DDAttachment", "value": "[{\"spaceId\":\"2256226585\",\"fileId\":\"xxx\",\"fileName\":\"xxx.xlsx\",\"fileType\":\"xlsx\",\"fileSize\":N}]"},
      {"name": "表格", "componentType": "TableField", "value": "", "details": [{"name": "表格", "rowValues": [{"name": "报表名称", "value": "xxx"}, {"name": "转账合计（元）", "value": "xxx"}, {"name": "扣款合计（五险一金、单位代理费）", "value": "xxx"}, {"name": "实发合计（元）", "value": "xxx"}, {"name": "个人所得税及其他", "value": "xxx"}]}]},
      {"name": "是否涉及五险一金缴费", "value": "是"},
      {"name": "备注", "value": ""}
    ]
  }
  ```

  **Test References**:
  - `/home/ubuntu/excel_example/paybill/approval_cache.json:formComponentValues` - 真实审批数据格式参考

  **External References**:
  - DingTalk API docs: https://open.dingtalk.com/document/development/create-an-approval-instance
  - 手机号查用户: https://open.dingtalk.com/document/orgapp/query-users-by-phone-number

  **WHY Each Reference Matters**:
  - PaySignPrinter的dingtalk_api.py是最直接的参考——相同的Token获取逻辑、错误处理模式
  - approval_cache.json提供了真实的formComponentValues格式，是验证创建格式正确性的关键
  - 钉钉API文档提供了官方接口定义

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test file created: tests/test_dingtalk_api.py
  - [ ] pytest tests/test_dingtalk_api.py → PASS

  **QA Scenarios:**

  ```
  Scenario: Token获取和缓存
    Tool: Bash (python)
    Steps:
      1. python -c "from dingtalk_api import get_access_token; t1=get_access_token(); t2=get_access_token(); print(t1==t2)"
    Expected Result: True (第二次使用缓存)
    Evidence: .omo/evidence/task-2-token-cache.txt

  Scenario: 手机号查询用户
    Tool: Bash (python)
    Steps:
      1. python -c "from dingtalk_api import get_user_by_mobile; uid=get_user_by_mobile('测试手机号'); print(uid)"
    Expected Result: 返回非空userId字符串
    Failure Indicators: None返回或异常
    Evidence: .omo/evidence/task-2-user-lookup.txt

  Scenario: 文件上传到钉钉空间
    Tool: Bash (python)
    Steps:
      1. python -c "from dingtalk_api import upload_file_to_space; fid=upload_file_to_space('/home/ubuntu/excel_example/paybill/吉林大学肿瘤研究所（A）2026年03月工资表.xlsx','2256226585'); print(fid)"
    Expected Result: 返回非空fileId字符串
    Failure Indicators: None返回或异常
    Evidence: .omo/evidence/task-2-file-upload.txt

  Scenario: 创建审批实例
    Tool: Bash (python)
    Steps:
      1. python -c 调用create_approval_instance创建测试审批
    Expected Result: 返回instanceId
    Failure Indicators: API错误或异常
    Evidence: .omo/evidence/task-2-create-approval.txt
  ```

  **Commit**: YES
  - Message: `feat(api): DingTalk API module with token, upload, approval, user lookup`
  - Files: `dingtalk_api.py, tests/test_dingtalk_api.py`
  - Pre-commit: `pytest tests/test_dingtalk_api.py -v`

- [ ] 3. Excel解析模块 (excel_parser.py)

  **What to do**:
  - TDD: 先写测试 `tests/test_excel_parser.py`
  - 实现 `excel_parser.py`，包含以下函数：
    - `parse_payroll_excel(file_path)` - 解析单个Excel工资表，返回PayrollSummary数据
    - `find_summary_row(ws)` - 在工作表中查找"合计"行（遍历A列查找"合计"关键字）
    - `find_column_index(ws, column_name)` - 在表头行（row 3-5）中查找指定列名的列索引
    - `extract_title_info(ws)` - 从C1单元格提取单位名称和年月信息
  - PayrollSummary结构（普通dict）：
    ```python
    {
      "unit_name": "吉林大学口腔医院",  # 从标题提取
      "year_month": "2026年04月",      # 从标题提取
      "report_name": "吉林大学口腔医院2026年04月人事代理人员工资发放表",  # C1完整标题
      "transfer_total": 504170.09,     # 转账合计
      "deduction_total": 143814.54,    # 扣款合计
      "net_total": 345277.56,          # 实发合计
      "tax_and_others": 15077.99       # 个人所得税及其他 = 转账合计-扣款合计-实发合计
    }
    ```
  - 列名匹配策略：
    - 在row 3中查找"转账合计"（精确匹配）
    - 在row 3中查找"扣款合计"（精确匹配）
    - 在row 3中查找"实发合计"（精确匹配）
    - 如果row 3未找到，扩展到row 4和row 5搜索
  - 数值处理：转换为float，保留2位小数
  - 使用 `openpyxl` 加载文件 (data_only=True)
  - 测试用例覆盖4个示例Excel文件

  **Must NOT do**:
  - 不使用pandas（openpyxl足够且更精确处理合并单元格）
  - 不添加Excel编辑功能
  - 不解析详细员工数据（只解析合计行）
  - 不创建dataclass或Pydantic模型（用普通dict）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Excel格式多变，合并单元格处理复杂，需要仔细调试
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 5, 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - 无直接参考（PaySignPrinter不解析Excel内容，只下载）

  **API/Type References**:
  - 测试文件1: `/home/ubuntu/excel_example/吉林大学口腔医院2026年04月工资表.xlsx` - 人事代理格式，31列，26人
    - C1="吉林大学口腔医院2026年04月人事代理人员工资发放表"
    - L列="转账合计", AB列="扣款合计", AE列="实发合计"
    - 合计行Row 32: L=504170.09, AB=143814.54, AE=345277.56
  - 测试文件2: `/home/ubuntu/excel_example/paybill/吉林大学中日联谊医院2026年03月工资表.xlsx` - 人事代理格式，31列，114人
    - C1="吉林大学中日联谊医院2026年03月人事代理人员工资发放表"
    - L列="转账合计", AA列="扣款合计", AE列="实发合计"
    - 合计行Row 119: L=1618715.56, AA=614689.38, AE=986892.15
  - 测试文件3: `/home/ubuntu/excel_example/paybill/吉林大学第一医院公共实验平台2026年04月工资表.xlsx` - 人才派遣格式，29列，1人
    - C1="吉林大学第一医院公共实验平台2026年04月人才派遣人员工资发放表"
    - K列="转账合计", Z列="扣款合计", AC列="实发合计"
    - 合计行Row 7: K=540, Z=40, AC=500
  - 测试文件4: `/home/ubuntu/excel_example/paybill/吉林大学肿瘤研究所（A）2026年03月工资表.xlsx` - 人才派遣格式，30列，1人
    - C1="吉林大学肿瘤研究所2026年03月人才派遣人员工资发放表"
    - L列="转账合计", AA列="扣款合计", AD列="实发合计"
    - 合计行Row 7: L=7887.69, AA=1887.69, AD=6000

  **Test References**:
  - 4个测试文件提供了不同的列布局和行数，用于验证解析的灵活性

  **WHY Each Reference Matters**:
  - 每个测试文件代表不同的甲方单位Excel格式，覆盖了列位置变化、列数差异、行数差异等关键变数
  - 精确的列位置和期望值用于编写精确的测试断言

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test file created: tests/test_excel_parser.py
  - [ ] pytest tests/test_excel_parser.py → PASS (覆盖4个示例文件)

  **QA Scenarios:**

  ```
  Scenario: 解析口腔医院Excel
    Tool: Bash (python)
    Steps:
      1. python -c "from excel_parser import parse_payroll_excel; r=parse_payroll_excel('/home/ubuntu/excel_example/吉林大学口腔医院2026年04月工资表.xlsx'); print(r['transfer_total'], r['deduction_total'], r['net_total'], r['tax_and_others'])"
    Expected Result: 504170.09 143814.54 345277.56 15077.99
    Failure Indicators: 值不匹配或异常
    Evidence: .omo/evidence/task-3-parse-kouqiang.txt

  Scenario: 解析不同格式Excel（第一医院）
    Tool: Bash (python)
    Steps:
      1. python -c "from excel_parser import parse_payroll_excel; r=parse_payroll_excel('/home/ubuntu/excel_example/paybill/吉林大学第一医院公共实验平台2026年04月工资表.xlsx'); print(r['transfer_total'], r['deduction_total'], r['net_total'])"
    Expected Result: 540 40 500
    Failure Indicators: 值不匹配或异常
    Evidence: .omo/evidence/task-3-parse-diyi.txt

  Scenario: 无合计行的Excel应报错
    Tool: Bash (python)
    Steps:
      1. 创建一个没有"合计"行的测试Excel
      2. 调用parse_payroll_excel
    Expected Result: 抛出ValueError，消息包含"未找到合计行"
    Evidence: .omo/evidence/task-3-no-summary.txt
  ```

  **Commit**: YES
  - Message: `feat(parser): Excel payroll parser with flexible column matching`
  - Files: `excel_parser.py, tests/test_excel_parser.py`
  - Pre-commit: `pytest tests/test_excel_parser.py -v`

- [ ] 4. 用户认证模块 (auth.py)

  **What to do**:
  - TDD: 先写测试 `tests/test_auth.py`
  - 实现 `auth.py`，包含以下函数：
    - `login(phone, password)` - 验证手机号和密码，返回用户信息
    - `get_dingtalk_user_id(phone)` - 通过手机号查询钉钉userId（调用dingtalk_api.get_user_by_mobile）
  - 用户存储：简单的JSON文件 `users.json`，格式 `[{"phone":"13800138000","password":"hashed","name":"王涵","dingtalk_user_id":"1855404625945034"}]`
  - 密码处理：使用hashlib.sha256简单哈希（不需要bcrypt，内部工具）
  - 初始化：如果users.json不存在，创建默认用户（从PaySignPrinter的user_mapping.json或.env获取）
  - Streamlit session_state管理：登录状态、当前用户信息

  **Must NOT do**:
  - 不实现JWT/OAuth等复杂认证
  - 不使用数据库
  - 不添加角色/权限系统
  - 不使用bcrypt（简单hash即可）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的用户认证，手机号+密码，JSON存储
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 5, 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/user_mapping.json` - 用户映射格式参考
  - `/home/ubuntu/excel_example/paybill/approval_cache.json:originatorUserId` - 已知userId=1855404625945034 (王涵)

  **API/Type References**:
  - 钉钉手机号查用户API: POST /topapi/v2/user/getbymobile → {"result":{"userid":"xxx"}}

  **WHY Each Reference Matters**:
  - user_mapping.json提供了已有的用户映射数据格式
  - 已知userId用于初始化默认用户

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test file created: tests/test_auth.py
  - [ ] pytest tests/test_auth.py → PASS

  **QA Scenarios:**

  ```
  Scenario: 正确手机号密码登录
    Tool: Bash (python)
    Steps:
      1. python -c "from auth import login; r=login('13800138000','test_password'); print(r['name'])"
    Expected Result: 返回用户名
    Failure Indicators: None返回或异常
    Evidence: .omo/evidence/task-4-login-success.txt

  Scenario: 错误密码登录
    Tool: Bash (python)
    Steps:
      1. python -c "from auth import login; r=login('13800138000','wrong_password'); print(r)"
    Expected Result: None
    Failure Indicators: 返回了用户信息
    Evidence: .omo/evidence/task-4-login-fail.txt

  Scenario: 手机号查询钉钉userId
    Tool: Bash (python)
    Steps:
      1. python -c "from auth import get_dingtalk_user_id; uid=get_dingtalk_user_id('手机号'); print(uid)"
    Expected Result: 返回非空userId
    Failure Indicators: None返回
    Evidence: .omo/evidence/task-4-userid-lookup.txt
  ```

  **Commit**: YES
  - Message: `feat(auth): phone number authentication module`
  - Files: `auth.py, tests/test_auth.py, users.json`
  - Pre-commit: `pytest tests/test_auth.py -v`

- [ ] 5. Streamlit主界面 - 文件上传与数据预览

  **What to do**:
  - 实现 `app.py` 的Streamlit主界面，包含以下区域：
    - **侧边栏**: 登录表单（手机号+密码），登录成功后显示用户信息和登出按钮
    - **主区域-文件上传**: `st.file_uploader` 支持多文件上传（accept multiple files, type=["xlsx","xls"]）
    - **主区域-数据预览**: 上传后自动解析，展示每个Excel的汇总数据表格
      - 表格列：单位名称、年月、转账合计、扣款合计、实发合计、个人所得税及其他
      - 显示自动生成的标题预览："XX、XX等X家单位XXXX年XX月工资发放请示"
    - **主区域-选择项**: "是否涉及五险一金缴费"下拉选择，"备注"文本框
    - **主区域-审批模板信息**: 显示processCode和spaceId
  - 使用 `st.session_state` 管理状态：登录状态、上传文件列表、解析结果
  - 解析结果缓存：避免重复解析同一文件
  - 错误显示：解析失败时用 `st.error()` 显示具体错误

  **Must NOT do**:
  - 不在此任务中实现审批提交（那是Task 6）
  - 不使用复杂的CSS/HTML模板
  - 不添加过度动画或交互

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Streamlit UI布局和交互设计
  - **Skills**: [`/frontend-ui-ux`]
    - `/frontend-ui-ux`: Streamlit UI设计最佳实践
  - **Skills Evaluated but Omitted**:
    - `playwright`: 不在此任务中做E2E测试

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential, depends on Wave 1)
  - **Blocks**: Task 6
  - **Blocked By**: Task 1, 2, 3, 4

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/app.py:1-100` - Streamlit应用结构、session_state管理、sidebar布局
  - `/home/ubuntu/coding/PaySignPrinter/app.py:st.session_state` - 状态管理模式

  **API/Type References**:
  - `excel_parser.py:parse_payroll_excel()` - 解析Excel返回的数据结构
  - `auth.py:login()` - 登录函数签名
  - `auth.py:get_dingtalk_user_id()` - 获取钉钉userId

  **WHY Each Reference Matters**:
  - PaySignPrinter的app.py是最直接的Streamlit模式参考
  - excel_parser和auth模块的函数签名决定了UI如何调用后端

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: 上传Excel文件并预览数据
    Tool: Playwright
    Steps:
      1. 启动 streamlit run app.py
      2. 在登录表单输入手机号和密码，点击登录
      3. 上传 /home/ubuntu/excel_example/吉林大学口腔医院2026年04月工资表.xlsx
      4. 检查预览表格是否显示：转账合计=504170.09, 扣款合计=143814.54, 实发合计=345277.56
      5. 检查标题预览包含"吉林大学口腔医院"
    Expected Result: 预览表格正确显示汇总数据，标题预览正确
    Failure Indicators: 数据为空或值不匹配
    Evidence: .omo/evidence/task-5-preview.png

  Scenario: 上传多个Excel文件
    Tool: Playwright
    Steps:
      1. 上传2个Excel文件（口腔医院+第一医院）
      2. 检查预览表格有2行数据
      3. 检查标题预览包含2家单位
    Expected Result: 2行数据，标题"吉林大学口腔医院、吉林大学第一医院公共实验平台等2家单位2026年04月工资发放请示"
    Failure Indicators: 只有1行或标题格式错误
    Evidence: .omo/evidence/task-5-multi-file.png

  Scenario: 上传无效文件
    Tool: Playwright
    Steps:
      1. 上传一个非Excel文件或损坏的Excel
    Expected Result: 显示错误消息
    Failure Indicators: 无错误提示或应用崩溃
    Evidence: .omo/evidence/task-5-invalid-file.png
  ```

  **Commit**: YES
  - Message: `feat(ui): Streamlit main interface with file upload and preview`
  - Files: `app.py`
  - Pre-commit: `python -c "import app; print('OK')"`

- [ ] 6. 审批提交集成

  **What to do**:
  - 在 `app.py` 中添加审批提交功能：
    - **提交按钮**: 仅在已上传文件且已解析数据时启用
    - **提交前确认**: `st.confirm_dialog` 或二次确认按钮
    - **提交流程**:
      1. 获取AccessToken
      2. 逐个上传Excel文件到钉钉空间，获取fileId列表
      3. 构建formComponentValues（标题、附件、TableField、选择项、备注）
      4. 调用create_approval_instance
      5. 显示审批创建结果（instanceId和链接）
    - **进度显示**: `st.progress` 或 `st.status` 显示上传和提交进度
    - **结果展示**: 成功时显示审批ID和钉钉审批链接；失败时显示详细错误
  - 构建formComponentValues的关键逻辑：
    ```python
    form_values = [
      {"name": "标题", "value": generated_title},
      {"name": "批量上传工资单", "componentType": "DDAttachment", "value": json.dumps([{"spaceId":"2256226585","fileId":"xxx","fileName":"xxx.xlsx","fileType":"xlsx","fileSize":N}])},
      {"name": "表格", "componentType": "TableField", "value": "", "details": table_details},
      {"name": "是否涉及五险一金缴费", "value": insurance_value},
      {"name": "备注", "value": remark_value}
    ]
    ```
  - TableField details构建：每个Excel对应一行rowValues
  - DDAttachment value：包含所有上传文件的fileId列表

  **Must NOT do**:
  - 不在提交前修改原始Excel文件
  - 不实现审批撤销功能
  - 不添加定时/批量提交

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 集成多个模块，需要处理API调用、状态管理、错误恢复等复杂逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential, after Task 5)
  - **Blocks**: Task 7, 8
  - **Blocked By**: Task 2, 3, 4, 5

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/app.py` - Streamlit按钮和状态管理模式

  **API/Type References**:
  - `dingtalk_api.py:upload_file_to_space()` - 文件上传函数签名
  - `dingtalk_api.py:create_approval_instance()` - 审批创建函数签名
  - 审批模板字段ID（见Task 2的formComponentValues格式）:
    - TextField-K2AD4O5B (标题)
    - DDAttachment_3MSRH0L7DLK0 (批量上传工资单)
    - TableField_3JSUH63IRKS0 (表格) with: TextField_RM4XC6255MO0, MoneyField_F81N6HQKK4G0, MoneyField_ZDQ7MP8CAXC0, MoneyField_2LGMPSHQL3Q0, CalculateField_LB0DK6OG4TS0
    - DDSelectField_1Q0KFXI857PC0 (是否涉及五险一金缴费)
    - TextareaField_D5F90M0Y72G0 (备注)
  - `/home/ubuntu/excel_example/paybill/approval_cache.json` - 真实审批数据格式参考

  **WHY Each Reference Matters**:
  - formComponentValues的正确格式是审批提交成功的关键
  - 字段ID必须与钉钉模板一致

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: 完整审批提交流程
    Tool: Playwright
    Steps:
      1. 登录后上传2个Excel文件
      2. 确认预览数据正确
      3. 点击"提交审批"按钮
      4. 确认二次确认弹窗
      5. 等待提交完成
      6. 检查是否显示instanceId
    Expected Result: 显示审批创建成功，包含instanceId
    Failure Indicators: 提交失败或无instanceId
    Evidence: .omo/evidence/task-6-submit-approval.png

  Scenario: 提交失败处理
    Tool: Bash (python)
    Steps:
      1. 模拟API错误（如token过期）
      2. 检查错误消息显示
    Expected Result: st.error显示具体错误信息
    Failure Indicators: 无错误提示或崩溃
    Evidence: .omo/evidence/task-6-error-handling.txt
  ```

  **Commit**: YES
  - Message: `feat(ui): approval submission integration`
  - Files: `app.py`
  - Pre-commit: `python -c "import app; print('OK')"`

- [ ] 7. 错误处理与边界情况

  **What to do**:
  - 完善 `app.py` 中的错误处理：
    - Token过期：自动刷新后重试
    - 文件上传失败：显示失败文件名，提示重试
    - 审批创建失败：显示DingTalk API错误码和消息
    - 手机号不在钉钉：提示"该手机号未在钉钉中注册"
  - Excel解析边界情况：
    - 无"合计"行：显示"未找到合计行，请检查Excel格式"
    - 列名未找到：显示"未找到'转账合计'列，请检查Excel表头"
    - 数值解析失败：显示具体单元格内容
    - 空文件：显示"Excel文件无数据"
    - 非Excel文件：文件类型过滤
  - 年月不一致检测：多个Excel文件来自不同月份时发出警告
  - 重复文件检测：同一文件上传两次时提示

  **Must NOT do**:
  - 不实现自动重试（除token刷新外）
  - 不添加复杂的错误分类系统
  - 不使用logging框架（用st.error/st.warning即可）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 在已有代码基础上添加错误处理，逻辑明确
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential, after Task 6)
  - **Blocks**: Task 8
  - **Blocked By**: Task 6

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/dingtalk_api.py` - 错误处理模式（try/except + status_code检查）

  **WHY Each Reference Matters**:
  - PaySignPrinter的错误处理模式简洁有效，值得参考

  **Acceptance Criteria**:

  **QA Scenarios:**

  ```
  Scenario: 无合计行的Excel
    Tool: Playwright
    Steps:
      1. 上传一个没有"合计"行的Excel
    Expected Result: st.error显示"未找到合计行"错误消息
    Evidence: .omo/evidence/task-7-no-summary-row.png

  Scenario: 非Excel文件上传
    Tool: Playwright
    Steps:
      1. 尝试上传一个.pdf文件
    Expected Result: 文件选择器只显示.xlsx/.xls文件
    Evidence: .omo/evidence/task-7-file-filter.png

  Scenario: Token过期自动刷新
    Tool: Bash (python)
    Steps:
      1. 设置过期token
      2. 调用需要认证的API
    Expected Result: 自动刷新token并成功调用
    Evidence: .omo/evidence/task-7-token-refresh.txt
  ```

  **Commit**: YES
  - Message: `fix: error handling and edge cases`
  - Files: `app.py, excel_parser.py, dingtalk_api.py`
  - Pre-commit: `pytest tests/ -v`

- [ ] 8. 集成测试与文档

  **What to do**:
  - 创建集成测试 `tests/test_integration.py`：
    - 端到端测试：上传Excel → 解析 → 构建formComponentValues → 验证数据格式
    - 多文件测试：3+个Excel文件的组合测试
    - 标题生成测试：验证"XX、XX等X家单位XXXX年XX月工资发放请示"格式
    - TableField格式验证：确保details/rowValues格式与钉钉API兼容
  - 创建 `.env.example` 最终版本（含所有变量和注释）
  - 创建 `README.md`：安装步骤、配置说明、使用说明（简明）
  - 确认所有pytest测试通过
  - 确认Streamlit应用可正常启动

  **Must NOT do**:
  - 不在集成测试中调用真实钉钉API（使用mock）
  - 不写长篇文档（README简洁即可）
  - 不添加CI/CD配置

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 测试编写和文档
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential, after Task 7)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 7

  **References**:

  **Pattern References**:
  - `/home/ubuntu/coding/PaySignPrinter/PROJECT_CONTEXT.md` - 项目文档格式参考（如需要）

  **WHY Each Reference Matters**:
  - PaySignPrinter的项目文档提供了文档结构参考

  **Acceptance Criteria**:

  **If TDD:**
  - [ ] Test file created: tests/test_integration.py
  - [ ] pytest tests/ -v → ALL PASS

  **QA Scenarios:**

  ```
  Scenario: 全部测试通过
    Tool: Bash
    Steps:
      1. pytest tests/ -v
    Expected Result: 所有测试PASS，0 failures
    Evidence: .omo/evidence/task-8-all-tests.txt

  Scenario: Streamlit应用启动
    Tool: Bash
    Steps:
      1. streamlit run app.py --server.headless true &
      2. sleep 3
      3. curl http://localhost:8501
    Expected Result: HTTP 200
    Evidence: .omo/evidence/task-8-streamlit-start.txt
  ```

  **Commit**: YES
  - Message: `test: integration tests and documentation`
  - Files: `tests/test_integration.py, README.md, .env.example`
  - Pre-commit: `pytest tests/ -v`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + linter. Review all changed files for: `as any`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 0**: `feat(api): add DingTalk API verification script` - verify_api.py
- **Task 1**: `feat(scaffold): project setup with dependencies and config` - requirements.txt, .env.example, config.py
- **Task 2**: `feat(api): DingTalk API module with token, upload, approval, user lookup` - dingtalk_api.py, tests/test_dingtalk_api.py
- **Task 3**: `feat(parser): Excel payroll parser with flexible column matching` - excel_parser.py, tests/test_excel_parser.py
- **Task 4**: `feat(auth): phone number authentication module` - auth.py, tests/test_auth.py
- **Task 5**: `feat(ui): Streamlit main interface with file upload and preview` - app.py
- **Task 6**: `feat(ui): approval submission integration` - app.py
- **Task 7**: `fix: error handling and edge cases` - *.py
- **Task 8**: `test: integration tests and documentation` - tests/

---

## Success Criteria

### Verification Commands
```bash
cd /home/ubuntu/coding/Payroll2DingTalk
pytest tests/ -v  # Expected: All tests pass
python verify_api.py  # Expected: All API verifications pass
streamlit run app.py  # Expected: App starts on port 8501
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] API verification script confirms all assumptions
- [ ] Real DingTalk approval can be created with test data
- [ ] Multiple Excel formats parse correctly
- [ ] Phone login works and returns correct userId
