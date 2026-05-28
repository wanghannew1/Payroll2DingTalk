# 钉钉审批附件上传 — 完整流程详解

> 本文档专门分析**上传Excel文件到钉钉审批钉盘**的完整过程，逐步骤说明每个接口的作用、输入输出、以及Python实现示例。
>
> **验证状态**：全部流程已通过实际API调用验证 ✅（2026-05-28）

---

## 目录
1. [总览：三步上传模型](#1-总览三步上传模型)
2. [Step 1：申请上传凭证](#2-step-1申请上传凭证)
3. [Step 2：直传文件到阿里云OSS](#3-step-2直传文件到阿里云oss)
4. [Step 3：提交确认，获取 fileId](#4-step-3提交确认获取-fileid)
5. [完整 Python 实现](#5-完整-python-实现)
6. [错误处理与常见问题](#6-错误处理与常见问题)

---

## 0. ⚠️ 前置条件：上传授权（每次上传前必须调用！）

**上传权限是临时的**，不是永久有效的。每次调用 Storage 上传 API 之前，必须先调用 `spaces/infos/query` 接口重新授权：

```
POST https://api.dingtalk.com/v1.0/workflow/processInstances/spaces/infos/query
x-acs-dingtalk-access-token: {accessToken}
```

```json
{
    "userId": "1855404625945034",
    "agentId": YOUR_AGENT_ID
}
```

这个接口有两个作用：
1. 获取 spaceId（同一企业内审批附件钉盘 spaceId 唯一）
2. **授予当前用户上传附件的权限**（核心！）

> **官方文档明确说明**："本接口有授权上传权限的作用。每次调用上传附件API接口前，建议使用上传操作人userId再调用一次本接口。"

**如果跳过此步骤直接调 Storage 上传，会返回 `403 permissionDenied`**。

---

## 1. 总览：四步上传模型（含授权）

钉钉审批附件的上传不是简单的一个"POST文件"接口，而是**三步异步流程**：

```
                   钉钉服务器
                       │
    ┌──────────────────┼──────────────────┐
    │  Step 1          │           Step 3 │
    │  申请上传凭证      │           提交确认 │
    │  (钉钉API)        │           (钉钉API)│
    ▼                  │                  ▼
 [你的服务] ═══════════════╪══════════════ [你的服务]
    │                    │                  ▲
    │     Step 2         │                  │
    │     直传文件到OSS    │                  │
    │     (非钉钉API)      │                  │
    ▼                    │                  │
 ┌──────────┐            │                  │
 │ 阿里云OSS │            │                  │
 └──────────┘            │                  │
                         │                  │
                    钉钉底层的                │
                    阿里云OSS存储             │
```

**为什么要三步？**
- 钉盘底层存储是阿里云OSS。为了**速度和带宽**，钉钉不让你把文件传到它的服务器再转存，而是给你一个**临时签名URL**直接上传到OSS。
- Step 1 相当于"预约"一个上传位置，Step 2 是实际传文件，Step 3 是"确认"入库。

---

## 2. Step 1：申请上传凭证

这是一个**钉钉API**。

### 2.1 接口定义

```
POST https://api.dingtalk.com/v1.0/storage/spaces/{spaceId}/files/uploadInfos/query?unionId={unionId}

Content-Type: application/json
x-acs-dingtalk-access-token: {accessToken}
```

### 2.2 路径参数

| 参数 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `spaceId` | string | [获取钉盘空间API] | 审批钉盘空间ID，固定值 `2256226585` |
| `unionId` | string(query) | [获取用户信息API] | 用户的unionId，用于鉴权 |

**关于 spaceId 的来源**：
```
POST /v1.0/workflow/processInstances/spaces/infos/query
→ 返回 {"result": {"spaceId": 2256226585}}
```

### 2.3 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `protocol` | string | **是** | 上传协议，固定为 `"HEADER_SIGNATURE"` |
| `multipart` | boolean | **是** | 是否分片上传。文件 < 5GB 传 `false`，≥5GB 传 `true` |
| `option.storageDriver` | string | 否 | 存储驱动，默认 `"DINGTALK"` |
| `option.preCheckParam.size` | long | 否 | 文件大小（字节），用于服务端校验 |
| `option.preCheckParam.parentId` | string | 否 | 父目录ID。根目录固定为 `"0"` |
| `option.preCheckParam.name` | string | 否 | 文件名（含扩展名），用于冲突检测 |

```json
{
  "protocol": "HEADER_SIGNATURE",
  "multipart": false,
  "option": {
    "storageDriver": "DINGTALK",
    "preCheckParam": {
      "size": 13054,
      "parentId": "0",
      "name": "吉林大学肿瘤研究所2026年03月工资表.xlsx"
    }
  }
}
```

### 2.4 响应体详解

```json
{
  "protocol": "HEADER_SIGNATURE",
  "uploadKey": "hgHOhntJGQLPAAAAM-VV8S0DAQShOAXaADkjaUFFSUFxUm1hV3hsQTZoNWRXNWthWE5yTUFUT0lUWGZud1hORF9BR3pKQUh6bW9YbkVzSXpRS3UGqERJTkdUQUxL",
  "storageDriver": "DINGTALK",
  "headerSignatureInfo": {
    "resourceUrls": [
      "https://sh-dualstack.trans.dingtalk.com/yundisk0/iAEIAqRmaWxlA6h5dW5kaXNrMATOITX..."
    ],
    "headers": {
      "Authorization": "OSS LTAI5tExample:signature=",
      "x-oss-date": "20260528T093716Z"
    },
    "expirationSeconds": 3600
  }
}
```

| 字段 | 用途 | 使用者 |
|------|------|--------|
| `uploadKey` | 上传凭证标识 | → Step 3 提交确认时用 |
| `headerSignatureInfo.resourceUrls[0]` | **OSS 上传地址** | → Step 2 直传文件时用 |
| `headerSignatureInfo.headers` | **OSS 鉴权签名头** | → Step 2 直传文件时用，证明你有权限写这个地址 |
| `headerSignatureInfo.expirationSeconds` | 签名有效期 | 通常 3600 秒（1小时），过期需重新申请 |

### 2.5 这个接口到底做了什么？

**用通俗的话说**：你打电话给钉钉前台说"我要放一个文件到档案室"，前台给你三样东西：
1. **uploadKey** — 一个取号小票，上面有你申请的编号（后面交文件时要用）
2. **resourceUrl** — 档案室旁边柜子的临时钥匙地址（文件先放到这个柜子里）
3. **ossHeaders** — 柜子的开柜密码（没有密码柜子开不了）

注意：这时候你还**没有传文件**，只是"预约"了一个位置。

### 2.6 这个接口的 URL 结构解析

```
POST https://api.dingtalk.com/v1.0/storage/spaces/{spaceId}/files/uploadInfos/query?unionId={unionId}
      ─────────────────────── ── ─────── ──────── ───── ──── ────────────── ────────
              │                │     │       │        │     │        │          │
              │                │     │       │        │     │        │          └── action: 查询上传信息
              │                │     │       │        │     │        │
              │                │     │       │        │     │        └── 目标: uploadInfos
              │                │     │       │        │     │
              │                │     │       │        │     └── 固定值 "0": 表示根目录下(不是指定文件ID)
              │                │     │       │        │
              │                │     │       │        └── 目标: files (钉盘文件)
              │                │     │       │
              │                │     │       └── 哪个空间: {spaceId} 审批附件空间
              │                │     │
              │                │     └── 模块: storage 存储模块
              │                │
              │                └── API 版本: v1.0
              │
              └── 钉钉 API 域名
```

---

## 3. Step 2：直传文件到阿里云OSS

这**不是钉钉API**！这是一个**阿里云OSS的PUT请求**。

### 3.1 来源

`resourceUrl` 和 `ossHeaders` 完全来自 Step 1 的响应：

```python
resource_url = response['headerSignatureInfo']['resourceUrls'][0]
oss_headers  = response['headerSignatureInfo']['headers']
```

### 3.2 请求格式

```
PUT {resource_url}

Header:
  Authorization: {oss_headers['Authorization']}
  x-oss-date:    {oss_headers['x-oss-date']}
  Content-Type:                                   ← ⚠️ 空字符串！不是 application/octet-stream！

Body:
  {文件的完整二进制内容}
```

### 3.3 为什么 Content-Type 必须是空字符串？

钉钉OSS上传要求 Content-Type 为空（这是阿里云OSS Header签名模式的要求）。
传 `application/octet-stream` 会导致签名校验失败。

```python
# ✅ 正确
headers = dict(oss_headers)
headers['Content-Type'] = ''

# ❌ 错误
headers = dict(oss_headers)
headers['Content-Type'] = 'application/octet-stream'  # 签名校验失败！
```

### 3.4 请求示例

```python
import requests

with open('/path/to/工资表.xlsx', 'rb') as f:
    file_binary = f.read()

resp = requests.put(
    resource_url,     # 从 Step 1 获取
    data=file_binary, # 文件二进制内容
    headers={
        'Authorization': oss_headers['Authorization'],
        'x-oss-date':    oss_headers['x-oss-date'],
        'Content-Type':  ''    # 必须空字符串
    },
    timeout=60
)

# 期望状态码 200
assert resp.status_code == 200, f"OSS上传失败: {resp.status_code}"
```

### 3.5 为什么不是钉钉API？

```
┌────────────────────────────────────────────────────────────┐
│                     上传路径对比                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   传统模式（慢）：                                          │
│   你的服务 ──20MB文件──▶ 钉钉服务器 ──20MB──▶ 阿里云OSS      │
│              ↑ 钉钉API          ↑ 内网转发                  │
│   你等两次网络传输，钉钉服务器成为瓶颈                        │
│                                                            │
│   直传模式（快）：                                          │
│   你的服务 ────────20MB文件────────▶ 阿里云OSS              │
│              ↑ 用钉钉给的临时签名URL，一次直达                │
│   无需经过钉钉服务器，速度快、带宽省                          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

`resource_url` 虽然域名里有 `dingtalk.com`，但它实际上是一个**阿里云OSS的内网代理地址**，请求直接命中OSS存储，不经过钉钉业务服务器。

### 3.6 resourceUrl 的有效期

`expirationSeconds` 通常为 **3600秒（1小时）**。如果你的服务需要长时间持有上传任务，注意过期前完成上传。

---

## 4. Step 3：提交确认，获取 fileId

这是一个**钉钉API**。

### 4.1 接口定义

```
POST https://api.dingtalk.com/v1.0/storage/spaces/{spaceId}/files/commit?unionId={unionId}

Content-Type: application/json
x-acs-dingtalk-access-token: {accessToken}
```

### 4.2 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `uploadKey` | string | **是** | 从 Step 1 获取的上传凭证 |
| `name` | string | **是** | 文件名（含扩展名） |
| `parentId` | string | **是** | 父目录ID。根目录固定为 `"0"` |
| `option.size` | long | 否 | 文件大小（字节） |
| `option.conflictStrategy` | string | 否 | 冲突策略 |

**冲突策略选项**：
| 值 | 说明 |
|-----|------|
| `AUTO_RENAME` | 自动重命名（默认）。文件名冲突时加后缀 `(1)`, `(2)` 等 |
| `OVERWRITE` | 覆盖已有文件 |
| `RETURN_DENTRY_IF_EXISTS` | 如果文件已存在，返回已有文件的dentry信息（不重复上传） |
| `RETURN_ERROR_IF_EXISTS` | 如果文件已存在，返回错误 |

```json
{
  "uploadKey": "hgHOhntJGQLPAAAAM-VV8S0DAQSh...",
  "name": "吉林大学肿瘤研究所2026年03月工资表.xlsx",
  "parentId": "0",
  "option": {
    "size": 13054,
    "conflictStrategy": "AUTO_RENAME"
  }
}
```

### 4.3 响应体详解

```json
{
  "dentry": {
    "id": "222892787485",                                  ← ⭐ 这就是 fileId！
    "name": "吉林大学肿瘤研究所2026年03月工资表(3).xlsx",     ← ⚠️ 实际文件名！
    "parentId": "0",
    "spaceId": "2256226585",
    "path": "/吉林大学肿瘤研究所（A）2026年03月工资表(3).xlsx",
    "size": 13054,
    "type": "FILE",
    "extension": "xlsx",
    "category": "DOCUMENT",
    "storageDriver": "DINGTALK",
    "status": "NORMAL",
    "version": 1,
    "uuid": "lyQod3RxJKxB07eks4o2zv3L8kb4Mw9r",
    "creatorId": "BiSiP0gVxBLoCDuJva79ii60QiEiE",
    "modifierId": "BiSiP0gVxBLoCDuJva79ii60QiEiE",
    "createTime": "Thu May 28 09:37:16 CST 2026",
    "modifiedTime": "Thu May 28 09:37:16 CST 2026"
  }
}
```

### 4.4 关键字段

| 字段 | 说明 |
|------|------|
| `dentry.id` | **fileId**。创建审批附件时用这个值 |
| `dentry.name` | **实际文件名**。如果用了 `AUTO_RENAME`，这里可能与原始文件名不同（如加了 `(3)` 后缀）。创建DDAttachment时必须用这个值 |
| `dentry.spaceId` | 文件所在的钉盘空间 |
| `dentry.size` | 文件实际大小 |

### 4.5 这个接口做了什么？

**用通俗的话说**：你拿着 Step 1 给的取号小票（uploadKey）去前台说"文件我已经放到柜子里了，帮我登记入库"。前台去检查柜子（OSS）里确实有这个文件，然后在档案本上登记，给你一个档案编号（fileId）。

---

## 5. 完整 Python 实现

### 5.1 单个文件上传

```python
import requests
import os
import json


def upload_file_to_dingtalk(file_path, space_id, union_id, access_token):
    """
    上传单个Excel文件到钉钉审批附件空间。

    Args:
        file_path:   本地文件路径
        space_id:    审批钉盘空间ID（从 getAttachmentSpace 获取）
        union_id:    用户unionId（从 get_user_info 获取）
        access_token: 新版API access_token

    Returns:
        dict: {"fileId": "222xxx", "fileName": "xxx.xlsx", "fileSize": 13054}
    """
    headers = {
        'x-acs-dingtalk-access-token': access_token,
        'Content-Type': 'application/json'
    }

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    # ──── Step 1：申请上传凭证 ────
    resp = requests.post(
        f'https://api.dingtalk.com/v1.0/storage/spaces/{space_id}/files/uploadInfos/query',
        headers=headers,
        params={'unionId': union_id},
        json={
            'protocol': 'HEADER_SIGNATURE',
            'multipart': False,
            'option': {
                'storageDriver': 'DINGTALK',
                'preCheckParam': {
                    'size': file_size,
                    'parentId': '0',
                    'name': file_name
                }
            }
        },
        timeout=10
    )

    if resp.status_code != 200:
        raise Exception(f'Step 1 失败: {resp.status_code} {resp.text}')

    data = resp.json()
    upload_key = data['uploadKey']
    resource_url = data['headerSignatureInfo']['resourceUrls'][0]
    oss_headers = data['headerSignatureInfo']['headers']

    # ──── Step 2：直传文件到OSS ────
    with open(file_path, 'rb') as f:
        file_binary = f.read()

    upload_headers = dict(oss_headers)
    upload_headers['Content-Type'] = ''  # ⚠️ 必须空字符串

    resp = requests.put(resource_url,
                        data=file_binary,
                        headers=upload_headers,
                        timeout=60)

    if resp.status_code != 200:
        raise Exception(f'Step 2 OSS上传失败: {resp.status_code}')

    # ──── Step 3：提交确认 ────
    resp = requests.post(
        f'https://api.dingtalk.com/v1.0/storage/spaces/{space_id}/files/commit',
        headers=headers,
        params={'unionId': union_id},
        json={
            'uploadKey': upload_key,
            'name': file_name,
            'parentId': '0',
            'option': {
                'size': file_size,
                'conflictStrategy': 'AUTO_RENAME'
            }
        },
        timeout=10
    )

    if resp.status_code != 200:
        raise Exception(f'Step 3 Commit失败: {resp.status_code} {resp.text}')

    dentry = resp.json()['dentry']

    return {
        'fileId': str(dentry['id']),
        'fileName': dentry['name'],  # 使用实际文件名（可能被重命名）
        'fileSize': dentry['size'],
        'spaceId': space_id,
        'fileType': dentry.get('extension', 'xlsx')
    }
```

### 5.2 批量上传（多文件）

```python
def batch_upload_files(file_paths, space_id, union_id, access_token):
    """
    批量上传多个Excel文件。

    返回的 attachment_list 可直接用于创建审批的 DDAttachment 字段。
    """
    attachments = []
    for file_path in file_paths:
        result = upload_file_to_dingtalk(file_path, space_id, union_id, access_token)
        attachments.append({
            'spaceId': result['spaceId'],
            'fileName': result['fileName'],
            'fileSize': result['fileSize'],
            'fileType': result['fileType'],
            'fileId': result['fileId']
        })
    return attachments


# 使用示例：构建审批的 DDAttachment 字段值
attachments = batch_upload_files(
    ['工资表1.xlsx', '工资表2.xlsx'],
    space_id='2256226585',
    union_id='BiSiP0gVxBLoCDuJva79ii60QiEiE',
    access_token=access_token
)

# 转换为 DDAttachment 值格式
attachment_value = json.dumps(attachments, ensure_ascii=False)
# 结果: '[{"spaceId":"2256226585","fileName":"工资表1.xlsx","fileSize":13054,"fileType":"xlsx","fileId":"222xxx"},...]'
```

### 5.3 完整调用链路（从手机号到审批创建）

```python
def full_approval_flow(phone_mobile, file_paths, title):
    """
    完整流程：手机号登录 → 上传文件 → 创建审批
    """
    # ──── Step 0: 准备 ────
app_key = 'YOUR_APP_KEY'
app_secret = 'YOUR_APP_SECRET'
    process_code = 'YOUR_PROCESS_CODE'

    # ──── 获取新版 Token ────
    resp = requests.post('https://api.dingtalk.com/v1.0/oauth2/accessToken',
                         json={'appKey': app_key, 'appSecret': app_secret})
    new_token = resp.json()['accessToken']

    # ──── 获取旧版 Token ────
    resp = requests.get('https://oapi.dingtalk.com/gettoken',
                        params={'appkey': app_key, 'appsecret': app_secret})
    old_token = resp.json()['access_token']

    # ──── 手机号 → userId ────
    resp = requests.post(
        f'https://oapi.dingtalk.com/topapi/v2/user/getbymobile?access_token={old_token}',
        json={'mobile': phone_mobile}
    )
    user_id = resp.json()['result']['userid']

    # ──── userId → unionId + deptId ────
    resp = requests.post(
        f'https://oapi.dingtalk.com/topapi/v2/user/get?access_token={old_token}',
        json={'userid': user_id, 'language': 'zh_CN'}
    )
    user_info = resp.json()['result']
    union_id = user_info['unionid']
    dept_id = user_info['dept_id_list'][0]

    # ──── 获取钉盘空间 ────
    resp = requests.post(
        'https://api.dingtalk.com/v1.0/workflow/processInstances/spaces/infos/query',
        headers={
            'x-acs-dingtalk-access-token': new_token,
            'Content-Type': 'application/json'
        },
        json={'userId': user_id, 'agentId': int(os.getenv('DINGTALK_AGENT_ID'))}
    )
    space_id = str(resp.json()['result']['spaceId'])

    # ──── 批量上传文件 ────
    headers_new = {
        'x-acs-dingtalk-access-token': new_token,
        'Content-Type': 'application/json'
    }

    attachments = []
    for file_path in file_paths:
        result = upload_file_to_dingtalk(file_path, space_id, union_id, new_token)
        attachments.append(result)

    # ──── 构造 TableField（6列，含新增甲方单位项目名称） ────
    # Excel第2行"单位名称：xxx" → 甲方单位项目名称
    table_rows = []
    for att in attachments:
        table_rows.append([
            {'name': '报表名称', 'value': att['fileName'].replace('.xlsx', '')},
            {'name': '甲方单位项目名称', 'value': '提取自Excel第2行'},
            {'name': '转账合计（元）', 'value': '0'},
            {'name': '扣款合计（五险一金、单位代理费）', 'value': '0'},
            {'name': '实发合计（元）', 'value': '0'},
            {'name': '个人所得税及其他', 'value': '0'}
        ])

    # ──── 构造表单值（模板已移除 是否涉及五险一金缴费） ────
    form_values = [
        {'name': '标题', 'value': title},
        {'name': '批量上传工资表', 'value': json.dumps(   # ← 字段名已改为 批量上传工资表
            [{'spaceId': a['spaceId'], 'fileName': a['fileName'],
              'fileSize': a['fileSize'], 'fileType': a['fileType'], 'fileId': a['fileId']}
             for a in attachments], ensure_ascii=False
        )},
        {'name': '表格', 'value': json.dumps(table_rows, ensure_ascii=False)},
        {'name': '备注', 'value': ''},
    ]

    # ──── 创建审批实例 ────
    resp = requests.post(
        'https://api.dingtalk.com/v1.0/workflow/processInstances',
        headers=headers_new,
        json={
            'processCode': process_code,
            'originatorUserId': user_id,
            'deptId': dept_id,                    # ⚠️ 必须！
            'formComponentValues': form_values,
            'title': title
        },
        timeout=30
    )

    return resp.json().get('instanceId')
```

---

## 6. 错误处理与常见问题

### 6.1 Step 1 失败

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `403 Forbidden.AccessDenied` | 缺少 `Storage.UploadInfo.Read` 权限 | 在钉钉后台开通此权限 |
| `400 MissingunionId` | 没传 unionId | 检查查询参数 `?unionId=xxx` |
| `400 paramError` | 参数格式错误 | 检查 protocol 是否为 `HEADER_SIGNATURE` |
| `500 systemError "Index: 0"` | **用了 v2.0 API！** | 换成 `/v1.0/storage/spaces/` |

### 6.2 Step 2 失败

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `403 Forbidden` | OSS签名过期或错误 | 重新执行 Step 1 获取新凭证 |
| `400 Bad Request` | Content-Type 设置错误 | 确保 `Content-Type: `（空字符串） |
| 超时 | 文件太大或网络问题 | 增加 timeout，大文件（>5GB）用分片上传 |

### 6.3 Step 3 失败

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `400 invalid uploadKey` | uploadKey 过期或无效 | 重新执行 Step 1-2-3 |
| `400 文件冲突` | 文件名相同且策略为 `RETURN_ERROR_IF_EXISTS` | 改用 `AUTO_RENAME` 或 `OVERWRITE` |

### 6.4 常见踩坑问题

**Q: 为什么我用 `/v2.0/storage/` 返回 500？**

A: v2.0 是旧版/内测版API，官方文档推荐使用 v1.0。换成：
```
POST /v1.0/storage/spaces/{spaceId}/files/uploadInfos/query
```

**Q: 为什么 `/media/upload` 上传的文件在审批里打不开？**

A: `/media/upload` 是IM消息接口，文件有时效限制。必须用本文档描述的 Storage API 流程。

**Q: 为什么上传成功但创建审批报 `sysErrror`？**

A: 缺少 `deptId` 参数！创建审批时必须传 `deptId`，虽然文档标为"非必填"。

**Q: uploadKey 能重复用吗？**

A: 不能。每个 uploadKey 对应一次上传，Step 2 完成后 uploadKey 即被消费。再上传需要重新 Step 1。

**Q: resourceUrl 多长时间过期？**

A: 响应中 `expirationSeconds` 字段标注，通常 3600 秒（1小时）。

---

## 附录：验证记录

| 时间 | 文件 | fileId | 空间 | 状态 |
|------|------|--------|------|------|
| 2026-05-28 09:37 | 吉林大学肿瘤研究所（A）2026年03月工资表.xlsx | 222892787485 | 2256226585 | ✅ 附件可正常打开 |
