# Payroll2DingTalk

> 工资单推送钉钉OA审批 — 单文件 Streamlit Demo

---

## 功能

用户通过手机号登录 → 上传多个 Excel 工资表 → 预览解析数据 → 一键提交钉钉 OA 审批流程。

## 运行

```bash
cd /home/ubuntu/coding/Payroll2DingTalk
streamlit run demo_app.py
```

浏览器打开 `http://localhost:8501`。

## 安装依赖

```bash
pip install streamlit requests openpyxl python-dotenv
```

## 环境配置

从 [钉钉开放平台](https://open-dev.dingtalk.com/) 获取以下配置：

| 配置项 | 获取路径 | 说明 |
|--------|----------|------|
| `DINGTALK_APP_KEY` | 应用开发 → 企业内部应用 → 应用信息 → AppKey | 应用的唯一标识 |
| `DINGTALK_APP_SECRET` | 应用开发 → 企业内部应用 → 应用信息 → AppSecret | 应用的密钥 |
| `DINGTALK_AGENT_ID` | 应用开发 → 企业内部应用 → 应用信息 → AgentId | 钉钉微应用编号 |
| `DINGTALK_PROCESS_CODE` | 钉钉管理后台 → OA审批 → 审批流程 → 流程编码 | OA 审批流程的唯一码 |

创建 `.env` 文件：

```env
DINGTALK_APP_KEY=YOUR_APP_KEY
DINGTALK_APP_SECRET=YOUR_APP_SECRET
DINGTALK_AGENT_ID=YOUR_AGENT_ID
DINGTALK_PROCESS_CODE=YOUR_PROCESS_CODE
```

## 钉钉权限配置

在 [钉钉开放平台](https://open-dev.dingtalk.com/) → 应用开发 → 企业内部应用 → 权限管理 中，必须开通以下权限：

### 必须开通（核心功能依赖）

| 权限点 | 用途 | 对应 API |
|--------|------|----------|
| `qyapi_base` | 获取 Access Token | `oauth2/accessToken`、`gettoken` |
| `qyapi_get_member_by_mobile` | 手机号查 userId | `topapi/v2/user/getbymobile` |
| `qyapi_get_member` | 查用户详情（unionId、deptId） | `topapi/v2/user/get` |
| `Workflow.Instance.Write` | 创建审批实例、授权上传空间 | `processInstances`、`spaces/infos/query` |
| `Storage.UploadInfo.Read` | 获取 OSS 上传凭证 | `uploadInfos/query` |
| `Storage.File.Write` | 提交文件上传确认 | `commit` |

### 建议保留（方便后续扩展）

| 权限点 | 用途 |
|--------|------|
| `Contact.User.Read` | 扩展通讯录功能 |
| `Workflow.Form.Read` | 动态获取审批模板字段 |
| `Workflow.Instance.Read` | 查询已提交审批单状态 |
| `Storage.File.Read` | 读取已上传的文件 |

### 不需要开通（本项目未使用）

| 权限点 | 说明 |
|--------|------|
| `Drive.Space.Read` / `Drive.Space.Write` / `Drive.SpaceManage.Read` | 钉盘 API，本项目使用 Storage API |
| `Storage.DownloadInfo.Read` | 下载文件用，本项目只上传 |
| `snsapi_base` | 网页 OAuth 授权，后端调用不需要 |

> **注意**：上传附件使用的是 **Storage API**（`Storage.UploadInfo.Read` + `Storage.File.Write`），不是 Drive API。如果开通 Drive 权限但文件上传仍然失败，请检查是否调用了正确的 Storage 接口。

## 常见问题

**登录报 400 错误**

1. 确认 `.env` 文件存在于项目根目录（与 `demo_app.py` 同级）
2. 确认 streamlit 从项目根目录启动：`streamlit run demo_app.py`（不是从子目录启动）
3. 重启 streamlit（配置加载只在启动时读取）

## 已验证的 API 链路

| 步骤 | API | 说明 |
|------|-----|------|
| 0 | `spaces/infos/query` | 每次上传前必须调用，授予临时上传权限 |
| 1 | `topapi/v2/user/getbymobile` | 手机号 → userId |
| 2 | `topapi/v2/user/get` | userId → unionId + deptId |
| 3 | Storage v1.0 `uploadInfos/query` | 获取 OSS 上传凭证 |
| 4 | PUT OSS | 直传文件二进制 |
| 5 | Storage v1.0 `commit` | 提交确认 → fileId |
| 6 | `processInstances` | 创建审批实例 |

## 文档

- `.omo/drafts/dingtalk-api-reference.md` — 钉钉 API 参考（含所有踩坑记录）
- `.omo/drafts/dingtalk-upload-flow.md` — 上传附件完整流程详解

## 技术栈

- Python 3.12
- Streamlit（Web UI）
- requests（HTTP）
- openpyxl（Excel 解析）
- python-dotenv（配置管理）

## 作者

wanghannew1
