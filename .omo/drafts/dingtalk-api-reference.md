# 钉钉OA审批接口文档 - Payroll2DingTalk

> **⚠️ 本文档基于实际API调用验证，所有接口均测试通过（2026-05-28）**
> 之前版本中部分API路径/格式有误，已全部修正。

## 目录
1. [完整调用链路总览](#0-完整调用链路总览)
2. [获取AccessToken](#1-获取accesstoken)
3. [手机号查询用户ID](#2-手机号查询用户id)
4. [获取用户unionId](#3-获取用户unionid)
5. [获取审批钉盘空间信息](#4-获取审批钉盘空间信息)
6. [上传附件到钉盘（Storage v1.0）](#5-上传附件到钉盘storage-v10)
7. [创建审批实例](#6-创建审批实例)
8. [获取审批表单Schema](#7-获取审批表单schema)
9. [OA表单组件值格式参考](#8-oa表单组件值格式参考)
10. [所需权限清单](#9-所需权限清单)
11. [踩坑记录](#10-踩坑记录)

---

## 0. 完整调用链路总览

```
用户输入手机号
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 1: 获取AccessToken                                      │
│   POST /v1.0/oauth2/accessToken → accessToken (缓存7200s)    │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 2: 手机号→userId                                        │
│   POST /topapi/v2/user/getbymobile → userId                  │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 3: userId→unionId                                       │
│   POST /topapi/v2/user/get → unionId, deptId                 │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 4: 获取审批钉盘空间ID                                    │
│   POST /v1.0/workflow/processInstances/spaces/infos/query    │
│   → spaceId                                                  │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 5: 上传Excel文件到钉盘（每个文件循环）                    │
│   5a. POST /v1.0/storage/spaces/{spaceId}/files/             │
│       uploadInfos/query → uploadKey, resourceUrl, ossHeaders  │
│   5b. PUT {resourceUrl} + 文件二进制 + ossHeaders             │
│   5c. POST /v1.0/storage/spaces/{spaceId}/files/commit       │
│       → fileId                                                │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 6: 创建审批实例                                          │
│   POST /v1.0/workflow/processInstances                       │
│   → instanceId                                               │
│                                                              │
│   ⚠️ 必须传 deptId 参数！                                     │
│   ⚠️ TableField 创建格式与读取格式不同！                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 1. 获取AccessToken

**用途**: 所有新版API (v1.0) 调用的鉴权凭证，有效期7200秒

```
POST https://api.dingtalk.com/v1.0/oauth2/accessToken
Content-Type: application/json
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| appKey | string | 是 | 应用Key |
| appSecret | string | 是 | 应用密钥 |

```json
{
  "appKey": "YOUR_APP_KEY",
  "appSecret": "YOUR_APP_SECRET"
}
```

### 响应体

| 字段 | 类型 | 说明 |
|------|------|------|
| accessToken | string | 访问令牌 |
| expireIn | int | 过期时间(秒)，默认7200 |

```json
{
  "accessToken": "fw8ef8we8f76e6f7s8dxxxx",
  "expireIn": 7200
}
```

### 使用方式

后续新版API调用在Header中携带：
```
x-acs-dingtalk-access-token: {accessToken}
Content-Type: application/json
```

旧版API（oapi）使用query参数：
```
?access_token={accessToken}
```

### Token管理建议
- 缓存token，在expireIn过期前复用
- 建议提前300秒刷新（即token使用6900秒后刷新）
- 不要每次API调用都重新获取token

---

## 2. 手机号查询用户ID

**用途**: 用户登录时，通过手机号获取钉钉userId

**⚠️ 使用旧版oapi域名，需要不同的access_token**

```
POST https://oapi.dingtalk.com/topapi/v2/user/getbymobile?access_token={oldAccessToken}
Content-Type: application/json
```

### 获取旧版Token

```
GET https://oapi.dingtalk.com/gettoken?appkey={appKey}&appsecret={appSecret}
```

响应：
```json
{
  "access_token": "xxx",
  "expires_in": 7200
}
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mobile | string | 是 | 手机号码 |

```json
{
  "mobile": "13944004547"
}
```

### 响应体

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "result": {
    "userid": "04686358251064375"
  }
}
```

### 所需权限
- `qyapi_get_member_by_mobile`（根据手机号获取成员基本信息权限）

---

## 3. 获取用户unionId

**用途**: 获取unionId和deptId，Storage API上传文件需要unionId，创建审批需要deptId

**⚠️ 使用旧版oapi域名**

```
POST https://oapi.dingtalk.com/topapi/v2/user/get?access_token={oldAccessToken}
Content-Type: application/json
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| userid | string | 是 | 用户userId |
| language | string | 否 | 语言（zh_CN/en_US），默认zh_CN |

```json
{
  "userid": "04686358251064375",
  "language": "zh_CN"
}
```

### 响应体

```json
{
  "errcode": 0,
  "errmsg": "ok",
  "result": {
    "userid": "04686358251064375",
    "unionid": "BiSiP0gVxBLoCDuJva79ii60QiEiE",
    "name": "艾丽",
    "mobile": "13944004547",
    "dept_id_list": [143412015],
    "title": "综合管理部副经理"
  }
}
```

### 关键字段
- **unionid**: Storage v1.0 API上传文件必须
- **dept_id_list**: 创建审批实例必须（取第一个部门ID即可）

### 所需权限
- `qyapi_get_member`（成员信息读权限）

---

## 4. 获取审批钉盘空间信息

**用途**: 获取审批附件上传所需的钉盘空间ID，**同时授权当前用户的上传权限**。

> **⚠️ 重要**：上传权限是临时的，每次调用 Storage 上传 API 前必须先调此接口重新授权。否则返回 `403 permissionDenied`。

```
POST https://api.dingtalk.com/v1.0/workflow/processInstances/spaces/infos/query
x-acs-dingtalk-access-token: {accessToken}
Content-Type: application/json
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agentId | long | 是 | 应用Agent ID |
| userId | string | 是 | 用户ID |

```json
{
  "agentId": YOUR_AGENT_ID,
  "userId": "04686358251064375"
}
```

### 响应体

```json
{
  "result": {
    "spaceId": 2256226585
  },
  "success": true
}
```

### 关键说明
- spaceId可缓存复用，同一应用+同一用户返回相同spaceId
- 已知spaceId: `2256226585`
- **建议**: 首次运行时调用此API获取spaceId，缓存后直接使用

### 所需权限
- `Workflow.Instance.Write`（工作流实例写权限）✅ 已开通

---

## 5. 上传附件到钉盘（Storage v1.0）

**用途**: 将Excel文件上传到钉盘审批空间，获取fileId用于审批附件

**⚠️ 这是核心上传流程，必须严格按顺序执行3步**

### 5.1 获取上传信息

**⚠️ 必须用 Storage v1.0 API，不是 v2.0！v2.0会返回500错误**

```
POST https://api.dingtalk.com/v1.0/storage/spaces/{spaceId}/files/uploadInfos/query?unionId={unionId}
x-acs-dingtalk-access-token: {accessToken}
Content-Type: application/json
```

#### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| spaceId | string | 钉盘空间ID（如"2256226585"） |

#### 查询参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| unionId | string | 是 | 用户unionId（从Step 3获取） |

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| protocol | string | 是 | 必须为 `"HEADER_SIGNATURE"` |
| multipart | boolean | 是 | 文件<5GB传`false`，>=5GB传`true` |
| option.storageDriver | string | 否 | 存储驱动，默认`"DINGTALK"` |
| option.preCheckParam.size | long | 否 | 文件大小（字节），用于校验 |
| option.preCheckParam.parentId | string | 否 | 父目录ID，根目录为`"0"` |
| option.preCheckParam.name | string | 否 | 文件名（含扩展名），用于冲突检测 |

```json
{
  "protocol": "HEADER_SIGNATURE",
  "multipart": false,
  "option": {
    "storageDriver": "DINGTALK",
    "preCheckParam": {
      "size": 13054,
      "parentId": "0",
      "name": "吉林大学肿瘤研究所（A）2026年03月工资表.xlsx"
    }
  }
}
```

#### 响应体

```json
{
  "protocol": "HEADER_SIGNATURE",
  "uploadKey": "hgHOhntJGQLPAAAAM-VV8S0DAQShOAXaADkjaUFFSUFxUm1hV3hsQTZoNWRXNWthWE5y...",
  "storageDriver": "DINGTALK",
  "headerSignatureInfo": {
    "resourceUrls": [
      "https://sh-dualstack.trans.dingtalk.com/yundisk0/iAEIAqRmaWxlA6h5dW5kaXNr..."
    ],
    "headers": {
      "Authorization": "OSS xxx:xxx",
      "x-oss-date": "20260528T093716Z"
    }
  }
}
```

#### 关键字段
- **uploadKey**: 提交文件时必须携带
- **headerSignatureInfo.resourceUrls[0]**: OSS上传地址
- **headerSignatureInfo.headers**: OSS上传必须的签名头

### 5.2 上传文件到OSS

```
PUT {headerSignatureInfo.resourceUrls[0]}
Authorization: {headerSignatureInfo.headers.Authorization}
x-oss-date: {headerSignatureInfo.headers.x-oss-date}
Content-Type: 
```

**⚠️ Content-Type 必须为空字符串（不是application/octet-stream）！**

#### Python示例

```python
with open(file_path, 'rb') as f:
    file_data = f.read()

upload_headers = dict(oss_headers)  # 从5.1响应的headers复制
upload_headers['Content-Type'] = ''  # 必须为空字符串！

resp = requests.put(resource_url, data=file_data, headers=upload_headers, timeout=60)
# 期望: resp.status_code == 200
```

### 5.3 提交文件（Commit）

```
POST https://api.dingtalk.com/v1.0/storage/spaces/{spaceId}/files/commit?unionId={unionId}
x-acs-dingtalk-access-token: {accessToken}
Content-Type: application/json
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| uploadKey | string | 是 | 从5.1响应获取 |
| name | string | 是 | 文件名（含扩展名） |
| parentId | string | 是 | 父目录ID，根目录为`"0"` |
| option.size | long | 否 | 文件大小（字节） |
| option.conflictStrategy | string | 否 | 冲突策略：`AUTO_RENAME`（默认） |

```json
{
  "uploadKey": "hgHOhntJGQLPAAAAM-VV8S0DAQSh...",
  "name": "吉林大学肿瘤研究所（A）2026年03月工资表.xlsx",
  "parentId": "0",
  "option": {
    "size": 13054,
    "conflictStrategy": "AUTO_RENAME"
  }
}
```

#### 响应体

```json
{
  "dentry": {
    "id": "222892787485",
    "name": "吉林大学肿瘤研究所（A）2026年03月工资表(3).xlsx",
    "parentId": "0",
    "spaceId": "2256226585",
    "size": 13054,
    "type": "FILE",
    "extension": "xlsx",
    "category": "DOCUMENT",
    "storageDriver": "DINGTALK",
    "status": "NORMAL",
    "createTime": "Thu May 28 09:37:16 CST 2026",
    "modifiedTime": "Thu May 28 09:37:16 CST 2026",
    "creatorId": "BiSiP0gVxBLoCDuJva79ii60QiEiE",
    "version": 1,
    "uuid": "lyQod3RxJKxB07eks4o2zv3L8kb4Mw9r"
  }
}
```

#### 关键字段
- **dentry.id**: 即为DDAttachment中的fileId
- **dentry.name**: 实际文件名（如果有冲突可能被自动重命名，如加了(3)后缀）
- ⚠️ 使用 `dentry.name` 作为DDAttachment中的fileName（而非原始文件名）

### 所需权限
- `Storage.UploadInfo.Read`（企业存储文件上传信息读权限）✅ 已开通
- `qyapi_get_member`（获取unionId用）✅ 已开通

---

## 6. 创建审批实例

**用途**: 发起钉钉OA审批流程

```
POST https://api.dingtalk.com/v1.0/workflow/processInstances
x-acs-dingtalk-access-token: {accessToken}
Content-Type: application/json
```

### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| processCode | string | 是 | 审批模板Code |
| originatorUserId | string | 是 | 发起人userId |
| **deptId** | **long** | **是** | **发起人部门ID（必须！否则报系统异常）** |
| formComponentValues | array | 是 | 表单控件值列表 |
| title | string | 是 | 审批标题 |

### ⚠️ deptId 是必填参数！

不传deptId会报 `sysErrror: 创建审批实例系统异常` 或 `processInstanceInvalidParameter`。
deptId从Step 3（获取用户信息）的 `dept_id_list` 字段获取，取第一个部门ID。

### 完整请求示例

```json
{
  "processCode": "YOUR_PROCESS_CODE",
  "originatorUserId": "1855404625945034",
  "deptId": 143412015,
  "formComponentValues": [
    {
      "name": "标题",
      "value": "长春市公路管理处、吉林大学第一医院公共实验平台等2家单位2026年02-04月工资发放请示"
    },
    {
      "name": "批量上传工资表",
      "value": "[{\"spaceId\":\"2256226585\",\"fileName\":\"长春市公路管理处2026年02月人才派遣人员工资发放表(1).xlsx\",\"fileSize\":12207,\"fileType\":\"xlsx\",\"fileId\":\"222931374187\"},{\"spaceId\":\"2256226585\",\"fileName\":\"吉林大学第一医院公共实验平台2026年04月人才派遣人员工资发放表(1).xlsx\",\"fileSize\":8340,\"fileType\":\"xlsx\",\"fileId\":\"222931433213\"}]"
    },
    {
      "name": "表格",
      "value": "[[{\"name\":\"报表名称\",\"value\":\"长春市公路管理处2026年02月人才派遣人员工资发放表\"},{\"name\":\"甲方单位项目名称\",\"value\":\"长春市公路管理处\"},{\"name\":\"转账合计（元）\",\"value\":\"20590.76\"},{\"name\":\"扣款合计（五险一金、单位代理费）\",\"value\":\"7790.76\"},{\"name\":\"实发合计（元）\",\"value\":\"12800.00\"},{\"name\":\"个人所得税及其他\",\"value\":\"0.00\"}],[{\"name\":\"报表名称\",\"value\":\"吉林大学第一医院公共实验平台2026年04月人才派遣人员工资发放表\"},{\"name\":\"甲方单位项目名称\",\"value\":\"吉林大学第一医院公共实验平台\"},{\"name\":\"转账合计（元）\",\"value\":\"540.00\"},{\"name\":\"扣款合计（五险一金、单位代理费）\",\"value\":\"40.00\"},{\"name\":\"实发合计（元）\",\"value\":\"500.00\"},{\"name\":\"个人所得税及其他\",\"value\":\"0.00\"}]]"
    },
    {
      "name": "备注",
      "value": ""
    }
  ],
  "title": "长春市公路管理处、吉林大学第一医院公共实验平台等2家单位2026年02-04月工资发放请示"
}
```

> **⚠️ 注意**: 模板中已无 `总计金额` 字段，该字段已被移除。TableField 的统计功能（`statField`）会自动计算各列的合计值。
```

### 响应体

```json
{
  "instanceId": "EC8GMH0_Q8-Sum4d3-f9nw08621779932944"
}
```

### 常见错误码

| code | 说明 | 解决方案 |
|------|------|---------|
| `Missingname` | 表单字段缺少name | 确保每个formComponentValue都有name字段 |
| `Missingvalue` | 表单字段缺少value | 确保每个formComponentValue都有value字段（空值传""） |
| `MissingoriginatorUserId` | 缺少发起人ID | 传入originatorUserId |
| `sysErrror` | 创建审批实例系统异常 | **可能原因**：①缺少deptId参数；②TableField格式错误（用了key而非name，或用了rowValue/rowNumber格式）；③传了模板不存在的字段（如总计金额） |
| `processInstanceInvalidParameter` | 审批实例参数错误 | 检查originatorUserId是否正确、是否传了deptId、发起人是否在发起部门中 |

### 所需权限
- `Workflow.Instance.Write`（工作流实例写权限）✅ 已开通

---

## 7. 获取审批表单Schema

**用途**: 通过processCode获取审批模板的表单结构（字段列表、控件类型、ID等），可用于动态获取控件ID而非硬编码

```
GET https://api.dingtalk.com/v1.0/workflow/forms/schemas/processCodes?processCode={processCode}
x-acs-dingtalk-access-token: {accessToken}
```

### 响应体（关键字段）

```json
{
  "result": {
    "schemaContent": {
      "items": [
        {
          "id": "TextField-K2AD4O5B",
          "name": "标题",
          "componentType": "TextField",
          "props": {"label": "标题", "required": true}
        },
        {
          "id": "DDAttachment_3MSRH0L7DLK0",
          "name": "批量上传工资单",
          "componentType": "DDAttachment"
        },
        {
          "id": "TableField_3JSUH63IRKS0",
          "name": "表格",
          "componentType": "TableField",
          "children": [
            {"id": "TextField_RM4XC6255MO0", "name": "报表名称", "componentType": "TextField"},
            {"id": "MoneyField_F81N6HQKK4G0", "name": "转账合计（元）", "componentType": "MoneyField"},
            {"id": "MoneyField_ZDQ7MP8CAXC0", "name": "扣款合计（五险一金、单位代理费）", "componentType": "MoneyField"},
            {"id": "MoneyField_2LGMPSHQL3Q0", "name": "实发合计（元）", "componentType": "MoneyField"},
            {"id": "CalculateField_LB0DK6OG4TS0", "name": "个人所得税及其他", "componentType": "CalculateField"}
          ]
        },
        {
          "id": "CalculateField_SSZ2HSRWJPC0",
          "name": "总计金额",
          "componentType": "CalculateField"
        },
        {
          "id": "DDSelectField_1Q0KFXI857PC0",
          "name": "是否涉及五险一金缴费",
          "componentType": "DDSelectField"
        },
        {
          "id": "TextareaField_D5F90M0Y72G0",
          "name": "备注",
          "componentType": "TextareaField"
        }
      ]
    }
  }
}
```

---

## 8. OA表单组件值格式参考

### 完整审批模板字段ID对照表（2026-05-28 更新）

| 字段名 | 组件类型 | ID | TableField子控件? |
|--------|---------|-----|-------------------|
| 标题 | TextField | TextField-K2AD4O5B | 否 |
| 批量上传工资表 | DDAttachment | DDAttachment_3MSRH0L7DLK0 | 否 |
| 表格 | TableField | TableField_3JSUH63IRKS0 | 否(容器) |
| 报表名称 | TextField | TextField_RM4XC6255MO0 | ✓ |
| 甲方单位项目名称 | TextField | TextField_1RIHUV1W1TQ80 | ✓ 新增 |
| 转账合计（元） | MoneyField | MoneyField_F81N6HQKK4G0 | ✓ |
| 扣款合计（五险一金、单位代理费） | MoneyField | MoneyField_ZDQ7MP8CAXC0 | ✓ |
| 实发合计（元） | MoneyField | MoneyField_2LGMPSHQL3Q0 | ✓ |
| 个人所得税及其他 | CalculateField | CalculateField_LB0DK6OG4TS0 | ✓ |
| 备注 | TextareaField | TextareaField_D5F90M0Y72G0 | 否 |

> **⚠️ 模板变更记录**：
> - 附件字段名从 `批量上传工资单` 改为 `批量上传工资表`
> - TableField 新增 `甲方单位项目名称` 列（来源：Excel 第2行的单位名称，如"吉林大学肿瘤研究所（A）"）
> - 移除 `是否涉及五险一金缴费` 和 `总计金额` 字段
> - TableField 通过 `statField` 自动生成合计行（含中文大写）

### DDAttachment值格式

创建时value为JSON字符串（必须JSON.stringify）：
> **字段名已从 `批量上传工资单` 改为 `批量上传工资表`**

```json
{
  "name": "批量上传工资表",
  "value": "[{\"spaceId\":\"2256226585\",\"fileName\":\"xxx.xlsx\",\"fileSize\":13054,\"fileType\":\"xlsx\",\"fileId\":\"222892787485\"}]"
}
```

**多文件附件**：数组中放多个对象即可：
```json
"value": "[{\"spaceId\":\"2256226585\",\"fileName\":\"工资表1.xlsx\",\"fileSize\":13054,\"fileType\":\"xlsx\",\"fileId\":\"111\"},{\"spaceId\":\"2256226585\",\"fileName\":\"工资表2.xlsx\",\"fileSize\":15000,\"fileType\":\"xlsx\",\"fileId\":\"222\"}]"
```

### TableField（表格/明细控件）格式 ⚠️ 关键！

**TableField 子控件引用使用 `name`（控件 label 名），不是 `key`（field ID）！**

**数据全部在字符串化的 `value` 字段中，不需要独立的 `details`、`rowValue` 等字段。**

#### 格式：`JSON.stringify( [[行1列], [行2列], ...] )`

```
value = "[[{name,value},...], [{name,value},...]]"
```

- 外层数组：每一行
- 内层数组：每一行中的列
- 每列：`{"name": "控件label名", "value": "值"}`
- ⚠️ `name` 使用的是 `props.label`（如"转账合计（元）"），不是 `id`（如"MoneyField_F81N6HQKK4G0"）

#### 验证成功的格式：

```json
{
  "name": "表格",
  "value": "[[{\"name\":\"报表名称\",\"value\":\"长春市公路管理处2026年02月人才派遣人员工资发放表\"},{\"name\":\"转账合计（元）\",\"value\":\"20590.76\"},{\"name\":\"扣款合计（五险一金、单位代理费）\",\"value\":\"7790.76\"},{\"name\":\"实发合计（元）\",\"value\":\"12800.00\"},{\"name\":\"个人所得税及其他\",\"value\":\"0.00\"}],[{\"name\":\"报表名称\",\"value\":\"吉林大学第一医院公共实验平台2026年04月人才派遣人员工资发放表\"},{\"name\":\"转账合计（元）\",\"value\":\"540.00\"},{\"name\":\"扣款合计（五险一金、单位代理费）\",\"value\":\"40.00\"},{\"name\":\"实发合计（元）\",\"value\":\"500.00\"},{\"name\":\"个人所得税及其他\",\"value\":\"0.00\"}]]"
}
```

#### Python 构造代码：

```python
# 构造表格数据：双层数组 → JSON.stringify
rows = [
    [
        {'name': '报表名称', 'value': '长春市公路管理处2026年02月人才派遣人员工资发放表'},
        {'name': '甲方单位项目名称', 'value': '长春市公路管理处'},  # ← 新增！来源：Excel第2行单位名称
        {'name': '转账合计（元）', 'value': '20590.76'},
        {'name': '扣款合计（五险一金、单位代理费）', 'value': '7790.76'},
        {'name': '实发合计（元）', 'value': '12800.00'},
        {'name': '个人所得税及其他', 'value': '0.00'}
    ],
    [
        {'name': '报表名称', 'value': '吉林大学第一医院公共实验平台2026年04月人才派遣人员工资发放表'},
        {'name': '甲方单位项目名称', 'value': '吉林大学第一医院公共实验平台'},
        {'name': '转账合计（元）', 'value': '540.00'},
        {'name': '扣款合计（五险一金、单位代理费）', 'value': '40.00'},
        {'name': '实发合计（元）', 'value': '500.00'},
        {'name': '个人所得税及其他', 'value': '0.00'}
    ]
]

table_value = json.dumps(rows, ensure_ascii=False)
# 结果: '[[{"name":"报表名称","value":"..."},...],[{"name":"报表名称","value":"..."},...]]'

form_values.append({'name': '表格', 'value': table_value})
```

#### ❌ 错误格式（会导致 sysErrror 或表格不显示）

| 错误 | 示例 | 原因 |
|------|------|------|
| 用 `key` 引用子控件 | `{"key":"MoneyField_F81N6HQKK4G0","value":"100"}` | 创建API需要 `name`（label名） |
| 用 `details` 独立字段 | `{"name":"表格","value":"","details":[...]}` | 数据应在 `value` 中 |
| 用 `rowValue` + `rowNumber` 格式 | `[{"rowValue":[...],"rowNumber":"..."}]` | 那是读取格式，不是创建格式 |
| 把 `details` 字符串化放 value 里 | `"value":"[{\"details\":[{\"rowValues\":[...]}]}]"` | 完全错误的嵌套 |

### MoneyField值格式

值为字符串类型的数字（保留2位小数）：
```json
{"name": "转账合计（元）", "value": "20590.76"}
```

### DDSelectField值格式

直接传选项文本：
```json
{"name": "是否涉及五险一金缴费", "value": "是"}
```

### CalculateField说明

TableField 中配置了 `statField`，系统会自动计算各 MoneyField 列的合计值（含中文大写金额），无需手动传总计字段。

---

### 📋 Excel → 表单字段映射规则

| 表单字段 | Excel 数据来源 | 示例 |
|---------|---------------|------|
| **报表名称** | Excel 第1行（标题行） | "吉林大学肿瘤研究所（A）2026年03月工资表" |
| **甲方单位项目名称** | Excel 第2行 `单位名称：` 后面的值 | "吉林大学肿瘤研究所（A）" |
| **转账合计（元）** | Excel 合计行的 `转账合计` 列 | 20590.76 |
| **扣款合计（五险一金、单位代理费）** | Excel 合计行的 `扣款合计` 列 | 7790.76 |
| **实发合计（元）** | Excel 合计行的 `实发合计` 列 | 12800.00 |
| **个人所得税及其他** | 计算：转账合计 - 扣款合计 - 实发合计 | 0.00 |

> Excel 列名可能因格式不同而有差异（如 `实发合计` vs `实发工资`），解析时需做列名模糊匹配。

---

### 📝 审批标题生成规则 ⚠️ 字数限制

审批标题有**字数限制**（TextField 最大长度约 64 字符），不能把所有单位都列在标题里。

**规则：只列出转账合计金额最大的 Top 2 单位，其余用"等X家"概括。**

| 单位数量 | 标题格式 | 示例 |
|---------|---------|------|
| 1 家 | `{单位名}{年}年{月}月工资发放请示` | 长春市公路管理处2026年02月工资发放请示 |
| 2 家 | `{单位1}、{单位2}{年}年{月}月工资发放请示` | 口腔医院、公路管理处2026年03月工资发放请示 |
| 3+ 家 | `{Top1转账合计单位}、{Top2转账合计单位}等{N}家单位{年}年{月}月工资发放请示` | 口腔医院、公路管理处等5家单位2026年03月工资发放请示 |

**年月提取规则**：从 Excel 文件名或标题行提取。如 `2026年03月`。

```python
# 示例：3家单位，按转账合计排序
# 口腔医院=500000, 公路管理处=20590, 公共实验平台=540
# → "吉林大学口腔医院、长春市公路管理处等3家单位2026年03月工资发放请示"
```

> **为什么选 Top 2**：确保标题在 64 字符以内。例如"XXXXX、XXXXX等100家单位2026年03月工资发放请示" ≈ 30+ 字符。

---

## 9. 所需权限清单

### 必须权限（已开通 ✅）

| 权限code | 权限名称 | 用途 |
|----------|---------|------|
| `Storage.UploadInfo.Read` | 企业存储文件上传信息读权限 | 上传文件到钉盘 |
| `qyapi_get_member` | 成员信息读权限 | 获取unionId和deptId |
| `qyapi_get_member_by_mobile` | 根据手机号获取成员基本信息权限 | 手机号登录 |
| `Workflow.Instance.Write` | 工作流实例写权限 | 创建审批+获取钉盘空间 |
| `Drive.Space.Read` | 钉盘应用中盘空间读权限 | 辅助（已开通） |
| `Drive.Space.Write` | 钉盘应用中盘空间写权限 | 辅助（已开通） |
| `Drive.SpaceManage.Read` | 钉盘应用盘空间管理信息读权限 | 辅助（已开通） |

### 不需要/不存在的权限

| 权限code | 说明 |
|----------|------|
| `Drive.UploadInfo.Read` | ❌ 不存在！钉钉已废弃此权限 |
| `Contact.User.Read` | 新版API，但无法通过userId查用户（返回404），用旧版oapi替代 |

---

## 10. 踩坑记录

### 坑1: /media/upload 上传的文件无法在审批中打开

**现象**: 用 `/v1.0/media/upload` 上传文件得到的mediaId，作为DDAttachment的fileId创建审批单，附件显示存在但点击提示"文件不存在或已过期"。

**原因**: `/media/upload` 是IM消息用的临时文件接口，文件有效期有限，不能用于审批钉盘永久附件。

**解决**: 必须使用 Storage v1.0 API 上传文件到钉盘空间。

---

### 坑2: Storage v2.0 API 返回 500 "Index: 0"

**现象**: 调用 `POST /v2.0/storage/spaces/files/0/uploadInfos/query` 返回500系统错误。

**原因**: v2.0是旧版/内测版API，官方文档推荐使用v1.0。

**解决**: 使用 `POST /v1.0/storage/spaces/{spaceId}/files/uploadInfos/query`

---

### 坑3: Drive API 返回 403 缺少 Drive.UploadInfo.Read 权限

**现象**: 调用 `GET /v1.0/drive/spaces/{spaceId}/files/0/uploadInfos` 返回403。

**原因**: `Drive.UploadInfo.Read` 权限在钉钉开发者后台不存在，已被废弃。

**解决**: 不要用Drive API，用Storage v1.0 API替代。

---

### 坑4: 新版Contact API /v1.0/contact/users/{userId} 返回404

**现象**: 调用新版API获取用户信息返回"找不到该用户"。

**原因**: 新版Contact API受应用可见范围限制，且权限模型不同。

**解决**: 使用旧版oapi `/topapi/v2/user/get`，配合 `qyapi_get_member` 权限。

---

### 坑5: 创建审批实例报 sysErrror

**现象**: 调用创建审批API返回 `{"code":"sysErrror","message":"创建审批实例系统异常"}`。

**原因**: **缺少 deptId 参数！** 官方文档标记deptId为"否"（非必填），但实际上不传就会报系统异常。

**解决**: 必须传 `deptId` 参数，值从用户信息接口 `dept_id_list` 字段获取。

---

### 坑6: OSS上传 Content-Type 不能是 application/octet-stream

**现象**: OSS上传返回错误。

**原因**: 钉盘OSS要求Content-Type为空字符串。

**解决**: PUT上传时设置 `Content-Type: `（空字符串）。

---

### 坑7: formComponentValues 必须同时有 name 和 value

**现象**: 返回 `Missingname` 或 `Missingvalue` 错误。

**原因**: 每个表单控件值必须同时包含name和value字段，即使是空值也需要传 `value: ""`。

**解决**: 确保每个formComponentValue对象都有name和value字段。

---

### 坑8: TableField 创建格式 ≠ 读取格式 ⚠️ 最重要！

**现象**: 包含 `表格` 字段时创建审批报 `sysErrror`，或创建成功但表格不显示。

**原因**: TableField 的创建格式与读取格式完全不同！

| | 创建格式 ✅ | 读取格式（仅用于查询） |
|---|---|---|
| 子控件引用 | `{"name": "转账合计（元）", "value": "100"}` | `{"label": "转账合计（元）", "key": "MoneyField_F81N6HQKK4G0", "value": "100"}` |
| 数据结构 | `value = "[[行1],[行2]]"` 字符串化双层数组 | `value = "[{\"rowValue\":[...],\"rowNumber\":\"...\"}]"` |
| 字段 | 只需 `name` + `value` | 含 `componentType`、`id`、`extValue` 等 |

**正确格式**:
```python
# 使用子控件的 label 名（如"转账合计（元）"），不是 field ID（如"MoneyField_F81N6HQKK4G0"）
rows = [
    [{'name': '报表名称', 'value': 'xx单位'}, {'name': '转账合计（元）', 'value': '100'}, ...],
    [{'name': '报表名称', 'value': 'yy单位'}, {'name': '转账合计（元）', 'value': '200'}, ...],
]
table_value = json.dumps(rows)  # 字符串化
form_values.append({'name': '表格', 'value': table_value})
```

---

### 坑9: 模板去掉了 `总计金额` 字段

**现象**: 传入 `总计金额` 字段可能导致 `sysErrror`。

**原因**: 当前模板（2026-05-28）中已无 `总计金额` 字段。TableField 通过 `statField` 自动统计各列合计值。

**解决**: 不要传 `总计金额` 字段，系统会在表格底部自动显示合计行。调用 `/workflow/forms/schemas/processCodes` 可获取最新模板结构。

---

### 坑10: 上传权限是临时的，每次上传前需重新授权 ⚠️

**现象**: 第一次上传成功，过一段时间后再上传返回 `403 permissionDenied`。

**原因**: 钉盘上传权限不是永久的！必须在上传前调用 `spaces/infos/query` 接口重新授权。

**解决**: 每次调用 Storage 上传 API 前，先调用：
```
POST /v1.0/workflow/processInstances/spaces/infos/query
```
此接口有两个作用：返回 spaceId + **授予当前用户上传权限**。官方文档明确说明："每次调用上传附件API接口前，建议使用上传操作人userId再调用一次本接口"。

---

## 已验证的完整测试记录

| 测试时间 | 操作 | 结果 | 备注 |
|---------|------|------|------|
| 2026-05-28 | /media/upload 上传 → 创建审批 | ⚠️ 创建成功但附件打不开 | mediaId是临时文件 |
| 2026-05-28 | Storage v2.0 上传 | ❌ 500 Index:0 | v2.0不可用 |
| 2026-05-28 | Drive v1.0 GET uploadInfos | ❌ 403 权限不足 | Drive.UploadInfo.Read不存在 |
| 2026-05-28 | Storage v1.0 上传 → 创建审批 | ✅ 附件可正常打开 | **正确方案** |
| 2026-05-28 | 创建审批不传deptId | ❌ sysErrror | 必须传deptId |
| 2026-05-28 | 创建审批传deptId | ✅ 创建成功 | instanceId: EC8GMH0_Q8-Sum4d3-f9nw08621779932944 |

### 成功的审批实例
- **instanceId**: `EC8GMH0_Q8-Sum4d3-f9nw08621779932944`
- **附件**: 吉林大学肿瘤研究所（A）2026年03月工资表.xlsx（Storage v1.0上传，fileId: 222895507851）
- **发起人**: 王涵 (userId: 1855404625945034, deptId: 143412015)
