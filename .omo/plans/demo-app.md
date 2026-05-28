# Demo App - 工资单上传钉钉审批

## TL;DR

> **Quick Summary**: 构建 Streamlit Web Demo，用户手机号登录 → 上传多个 Excel 工资表 → 预览解析结果 → 一键提交钉钉OA审批
>
> **Estimated Effort**: Quick (单文件 Streamlit app)
> **Test Strategy**: 手动测试 (Step 0 提供验证脚本)

---

## Context

### 已验证的 API 链路（全部通过 ✅）

| Step | API | 关键点 |
|------|-----|--------|
| 0 | `spaces/infos/query` | ⚠️ 每次上传前必须调用，授予临时上传权限 |
| 1 | `topapi/v2/user/getbymobile` | 手机号→userId（旧版 oapi） |
| 2 | `topapi/v2/user/get` | userId→unionId + deptId（旧版 oapi） |
| 3 | Storage v1.0 `uploadInfos/query` | 获取 OSS 上传凭证（⚠️ 用 v1.0 非 v2.0） |
| 4 | PUT OSS | 直传文件二进制（Content-Type 必须空字符串） |
| 5 | Storage v1.0 `commit` | 提交确认→获取 fileId |
| 6 | `processInstances` | 创建审批（⚠️ 必须传 deptId） |

### 当前模板结构（2026-05-28）

```
表单字段（4个）:
  1. 标题 (TextField) - 标签名"标题"
  2. 批量上传工资表 (DDAttachment) - 标签名"批量上传工资表"
  3. 表格 (TableField, 6列):
     - 报表名称 (TextField_RM4XC6255MO0)
     - 甲方单位项目名称 (TextField_1RIHUV1W1TQ80) ← 新增
     - 转账合计（元） (MoneyField_F81N6HQKK4G0)
     - 扣款合计(五险一金、单位代理费) (MoneyField_ZDQ7MP8CAXC0)
     - 实发合计（元） (MoneyField_2LGMPSHQL3Q0)
     - 个人所得税及其他 (CalculateField_LB0DK6OG4TS0)
  4. 备注 (TextareaField)
```

### TableField 创建格式（关键！）

```python
# value = JSON.stringify( [[行1],[行2],...] )
# 子控件用 name(label名)，不是 key(field ID)
table_value = json.dumps([
    [{'name': '报表名称', 'value': '...'},
     {'name': '甲方单位项目名称', 'value': '...'},
     {'name': '转账合计（元）', 'value': '20590.76'},
     {'name': '扣款合计（五险一金、单位代理费）', 'value': '7790.76'},
     {'name': '实发合计（元）', 'value': '12800.00'},
     {'name': '个人所得税及其他', 'value': '0.00'}],
    # ... more rows
], ensure_ascii=False)
```

### 标题生成规则

```
1家  → "{单位}{年月}工资发放请示"
2家  → "{单位1}、{单位2}{年月}工资发放请示"      ← 不用"等"
3+家 → "{Top1}、{Top2}等{N}家单位{年月}工资发放请示"
```

---

## Work Objectives

### Core Objective
构建单文件 Streamlit Demo App (`demo_app.py`)，完整实现"手机号登录 → 上传Excel → 预览数据 → 创建审批"

### Concrete Deliverable
- `/home/ubuntu/coding/Payroll2DingTalk/demo_app.py` — 完整 Streamlit 应用

### Must Have
- 手机号输入登录
- 多文件 Excel 上传（st.file_uploader accept_multiple_files=True）
- 数据预览表格（st.dataframe 显示每个文件的解析结果）
- "提交审批"按钮（一键上传+创建）
- 结果展示（instanceId、标题预览）
- .env 配置读取（APP_KEY, APP_SECRET, AGENT_ID, PROCESS_CODE）

### Must NOT Have
- 数据库持久化
- 用户管理/多账号
- 审批单查询/管理

### Excel 数据解析规则
1. **单位名称**: 从第2行提取（`单位名称：xxx` 后面的值）
2. **报表名称**: 从第1行提取（完整标题如"长春市公路管理处2026年02月人才派遣人员工资发放表"）
3. **年月**: 从文件名或标题行提取（如"2026年02月"）
4. **汇总行**: 第一列包含"合计"的行
5. **转账合计/扣款合计/实发合计**: 从汇总行按列名模糊匹配

---

## 文件结构

```
demo_app.py          ← 唯一下载
├── 配置读取 (.env)
├── 手机号登录
├── 钉钉API工具函数类 DingTalkClient
├── Excel 解析函数
├── Streamlit UI 页面
└── main()
```

---

## TODOs

---

- [x] 1. 基础架构：config + DingTalkClient 类 + Streamlit 页面框架

  **What to do**:
  - 创建 `/home/ubuntu/coding/Payroll2DingTalk/demo_app.py`
  - 从 `.env` 读取 APP_KEY, APP_SECRET, AGENT_ID, PROCESS_CODE
  - 创建 `DingTalkClient` 类封装 token 管理（含自动刷新）
  - Streamlit 页面设置（标题、布局）
  - 页面框架：手机号输入区 → 文件上传区 → 预览区 → 提交区

  **Must NOT do**:
  - 不要创建多个文件（单文件 app）
  - 不要引入第三方钉钉 SDK（只用 requests）

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - Justification: 基础文件结构，简单直接

  **Parallelization**: Wave 1 | Blocked By: None | Blocks: All other tasks

  **Acceptance Criteria**:
  - [ ] `python demo_app.py` 启动不报错
  - [ ] Streamlit 页面可访问（localhost:8501）
  - [ ] 手机号输入框可见

  **QA Scenarios**:

  ```
  Scenario: 启动Demo App
    Tool: interactive_bash (tmux)
    Preconditions: .env 文件存在且有正确配置
    Steps:
      1. Run: streamlit run demo_app.py --server.port 8501
      2. Wait for "You can now view your Streamlit app in your browser"
      3. Check: curl http://localhost:8501 returns HTTP 200
    Expected Result: Streamlit 运行正常，浏览器返回 200
    Evidence: .omo/evidence/task-1-startup.txt
  ```

  **Commit**: NO

---

- [x] 2. 手机号登录：调用 oapi 获取 userId + unionId + deptId

  **What to do**:
  - 在 `DingTalkClient` 中实现 `get_old_token()` 获取旧版 access_token
  - 实现 `get_user_by_mobile(mobile) → userId`
  - 实现 `get_user_info(user_id) → (union_id, dept_id, user_name)`
  - Streamlit 中：输入手机号 → 点击"登录"按钮 → 获取用户信息 → session_state 存储

  **Must NOT do**:
  - 不要用新版 Contact API（v1.0/contact/users，会因可见范围返回404）

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**: Wave 1 | Blocked By: Task 1 | Blocks: Task 3, 5

  **Acceptance Criteria**:
  - [ ] 输入手机号 `13944004547` 点击登录，能获取 userId 和 name
  - [ ] 登录成功后显示 "已登录: 王涵"

  **References**:
  - `.omo/drafts/dingtalk-api-reference.md` 第2节（手机号查询用户ID）
  - `.omo/drafts/dingtalk-api-reference.md` 第3节（获取用户unionId）
  - Old API: `POST /topapi/v2/user/getbymobile?access_token={old_token}`
  - Old API: `POST /topapi/v2/user/get?access_token={old_token}`

  **QA Scenarios**:

  ```
  Scenario: 手机号登录成功
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8501
      2. Type "13944004547" in mobile input field
      3. Click "登录" button
      4. Assert text "已登录: 王涵" or "欢迎, 艾丽" appears
      5. Screenshot: .omo/evidence/task-2-login.png
    Expected Result: 登录成功，显示用户姓名

  Scenario: 手机号格式错误
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8501
      2. Type "12345" in mobile input field
      3. Click "登录" button
      4. Assert error message appears
    Expected Result: 显示手机号格式错误提示
    Evidence: .omo/evidence/task-2-error.png
  ```

  **Commit**: YES | Message: `feat: phone login via DingTalk oapi`

---

- [x] 3. Excel 解析：提取单位名称、年报、汇总行数据

  **What to do**:
  - 实现函数 `parse_excel(file_bytes, filename) → dict`
  - 用 openpyxl 读取 Excel（data_only=True）
  - 从第1行提取"报表名称"（完整标题文本）
  - 从第2行提取"甲方单位项目名称"（`单位名称：`/`名称：`后的值）
  - 从文件名或标题行提取年月（如 "2026年03月"）
  - 找到"合计"行（第一列="合计"）
  - 从合计行按列名模糊匹配提取：转账合计、扣款合计、实发合计
  - 计算个人所得税及其他 = 转账合计 - 扣款合计 - 实发合计
  - 返回结构化 dict

  **列名模糊匹配规则**:
  ```
  转账合计: "转账合计" in cell_text
  扣款合计: "扣款合计" in cell_text or "扣款" in cell_text
  实发合计: "实发合计" in cell_text or "实发" in cell_text
  ```

  **Must NOT do**:
  - 不要硬编码列位置（不同Excel格式列位置不同）

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**: Wave 1 | Blocked By: Task 1 | Blocks: Task 4, 5

  **Acceptance Criteria**:
  - [ ] 解析长春市公路管理处文件 → 提取出单位名"长春市公路管理处"
  - [ ] 解析吉林大学肿瘤研究所文件 → 提取出单位名"吉林大学肿瘤研究所（A）"
  - [ ] 转账合计/扣款合计/实发合计数值正确

  **References**:
  - `/home/ubuntu/excel_example/paybill/长春市公路管理处2026年02月工资表_20.xlsx` — Row 1=标题, Row 2=单位名称, Row 10=合计
  - `/home/ubuntu/excel_example/paybill/吉林大学肿瘤研究所（A）2026年03月工资表.xlsx` — 不同格式参照
  - `.omo/drafts/dingtalk-api-reference.md` Excel→表单映射规则

  **QA Scenarios**:

  ```
  Scenario: 解析长春市公路管理处工资表
    Tool: Bash
    Steps:
      1. python3 -c "import demo_app; r = demo_app.parse_excel(open('.../长春市公路管理处...xlsx','rb').read(), 'test.xlsx')"
      2. Assert r['unit_name'] == '长春市公路管理处'
      3. Assert r['转账合计'] == 20590.76
      4. Assert r['扣款合计'] == 7790.76
      5. Assert r['实发合计'] == 12800.00
      6. Assert r['个税及其他'] == 0.00
    Expected Result: 所有字段提取正确
    Evidence: .omo/evidence/task-3-parse.txt
  ```

  **Commit**: YES | Message: `feat: Excel payroll data parser`

---

- [x] 4. 文件上传 + 审批创建：完整 API 调用链

  **What to do**:
  - 在 `DingTalkClient` 中实现：
    - `authorize_upload(user_id, agent_id)` → spaceId（每次上传前调用）
    - `upload_file(file_path, union_id, space_id) → {fileId, fileName, fileSize}`
    - `create_approval(user_id, dept_id, title, attachments, table_rows, note) → instanceId`
  - 文件上传步骤：authorize → uploadInfos/query → PUT OSS → commit
  - 审批创建用正确格式：
    - 附件字段名：`批量上传工资表`
    - TableField value：`json.dumps([[行1],[行2]])` 格式，子控件用 name
    - 不传 `是否涉及五险一金缴费` 和 `总计金额`（模板已移除）
  - 标题按规则生成

  **Must NOT do**:
  - 不要忘记 deptId（创建审批必须传）
  - 不要用 v2.0 Storage API（报500）
  - 不要用 details 字段存 TableField 数据

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - Justification: 涉及多步API调用和格式转换，需要仔细实现

  **Parallelization**: Wave 2 | Blocked By: Task 1, 2, 3 | Blocks: None

  **Acceptance Criteria**:
  - [ ] 单文件上传成功获取 fileId
  - [ ] 2文件上传成功获取2个 fileId
  - [ ] 创建审批成功返回 instanceId
  - [ ] 创建3附件审批，表格显示6列

  **References**:
  - `.omo/drafts/dingtalk-api-reference.md` — 完整API格式（第5、6节）
  - `.omo/drafts/dingtalk-upload-flow.md` — 上传流程详解
  - Storage v1.0: `POST /v1.0/storage/spaces/{spaceId}/files/uploadInfos/query?unionId={unionId}`
  - Commit: `POST /v1.0/storage/spaces/{spaceId}/files/commit?unionId={unionId}`
  - Create: `POST /v1.0/workflow/processInstances`

  **QA Scenarios**:

  ```
  Scenario: 完整流程 — 上传2个文件并创建审批
    Tool: Playwright
    Steps:
      1. Navigate to http://localhost:8501
      2. Login with phone "13944004547"
      3. Upload 2 Excel files
      4. Click "开始上传并提交"
      5. Wait for progress bar to complete
      6. Assert "审批单已创建" appears
      7. Assert instanceId is displayed
    Expected Result: 审批单创建成功，显示实例ID
    Evidence: .omo/evidence/task-4-success.png

  Scenario: 上传失败显示错误
    Tool: Playwright
    Steps:
      1. Login
      2. Upload invalid file (non-Excel)
      3. Click submit
      4. Assert error message "无法解析文件" or similar
    Expected Result: 友好的错误提示
    Evidence: .omo/evidence/task-4-error.png
  ```

  **Commit**: YES | Message: `feat: DingTalk upload + approval creation API`

---

- [x] 5. Streamlit UI：文件上传、数据预览、提交按钮

  **What to do**:
  - 文件上传区：`st.file_uploader("上传工资表", type=["xlsx"], accept_multiple_files=True)`
  - 数据预览：用 `st.dataframe` 展示解析结果表格
    - 列：单位名称 | 报表名称 | 年月 | 转账合计 | 扣款合计 | 实发合计 | 个人所得税及其他
  - 提交区：
    - 显示自动生成的标题预览
    - "提交审批"按钮（st.button）
    - 进度条（上传每个文件时更新）
    - 结果展示（instanceId + 成功/失败状态）
  - 状态管理：用 `st.session_state` 保持登录状态和解析结果

  **Must NOT do**:
  - 不要复杂的状态管理
  - 不需要异步处理

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `["frontend-ui-ux"]`
  - Justification: Streamlit UI 需要良好的用户体验设计

  **Parallelization**: Wave 3 | Blocked By: Task 2, 3, 4 | Blocks: None

  **Acceptance Criteria**:
  - [ ] 登录后文件上传区出现
  - [ ] 上传文件后预览表格正确显示
  - [ ] 标题预览符合 Top 2 规则
  - [ ] 点击提交后显示进度和结果

  **QA Scenarios**:

  ```
  Scenario: 完整 UI 流程
    Tool: Playwright
    Preconditions: 已登录
    Steps:
      1. Upload 3 Excel files
      2. Verify preview table shows 3 rows
      3. Verify title preview shows "Top1、Top2等3家单位..."
      4. Click "提交审批"
      5. Wait for progress bar
      6. Assert success message with instanceId
    Expected Result: 完整流程走通
    Evidence: .omo/evidence/task-5-full-flow.png
  ```

  **Commit**: YES | Message: `feat: Streamlit UI with preview and submit`

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  验证所有 API 调用格式与文档一致：TableField 用 name 非 key、deptId 必传、上传前调 authorize。

- [x] F2. **Code Quality Review** — `unspecified-high`
  检查：Token 管理、错误处理、进度反馈、代码组织。

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright`)
  完整走一遍：登录→上传→预览→提交→验证审批单在钉钉客户端可查看。

- [x] F4. **Scope Fidelity Check** — `deep`
  确认单文件结构、无多余依赖、所有必须功能已实现。

---

## Success Criteria

### 功能验证
- [ ] 手机号登录流程正常
- [ ] 单文件/多文件上传正常
- [ ] Excel 解析数据正确（含6列聚合）
- [ ] 创建审批成功，附件和表格显示正常
- [ ] 标题生成符合 Top 2 规则

### 运行命令
```bash
cd /home/ubuntu/coding/Payroll2DingTalk
streamlit run demo_app.py
```
