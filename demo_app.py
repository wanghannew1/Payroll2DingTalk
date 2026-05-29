import os
import re
import json
import time
from io import BytesIO

import requests
import openpyxl
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

APP_KEY = os.getenv("DINGTALK_APP_KEY", "")
APP_SECRET = os.getenv("DINGTALK_APP_SECRET", "")
AGENT_ID = int(os.getenv("DINGTALK_AGENT_ID", "0") or "0")
PROCESS_CODE = os.getenv("DINGTALK_PROCESS_CODE", "")

DEFAULT_CONFIG = {
    "excel": {
        "summary_row_marker": "合计",
        "unit_name_patterns": [
            r"(?:单位名称[：:]|[名称][：:]\s*)(.+?)(?:\s|$)"
        ],
        "columns": {
            "transfer_total": {
                "keywords": ["转账合计"],
                "label": "转账合计（元）"
            },
            "deduction_total": {
                "keywords": ["扣款合计", "扣款"],
                "label": "扣款合计（五险一金、单位代理费）"
            },
            "net_total": {
                "keywords": ["实发合计", "实发工资", "实发"],
                "label": "实发合计（元）"
            }
        }
    },
    "table_field": {
        "columns": [
            {"key": "report_name", "label": "报表名称"},
            {"key": "unit_name", "label": "甲方单位项目名称"},
            {"key": "transfer_total", "label": "转账合计（元）"},
            {"key": "deduction_total", "label": "扣款合计（五险一金、单位代理费）"},
            {"key": "net_total", "label": "实发合计（元）"},
            {"key": "tax_and_others", "label": "个人所得税及其他"}
        ]
    }
}


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG


CONFIG = load_config()


class DingTalkClient:
    def __init__(self, app_key, app_secret, agent_id, process_code):
        self.app_key = app_key
        self.app_secret = app_secret
        self.agent_id = agent_id
        self.process_code = process_code
        self.new_token = None  # v1.0 API token
        self.old_token = None  # oapi token
        self.token_expires = 0

    def _ensure_tokens(self):
        """Auto-refresh tokens if expired or not set."""
        now = time.time()
        if self.new_token and self.old_token and now < (self.token_expires - 300):
            return

        # New token (v1.0)
        resp = requests.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken",
            json={"appKey": self.app_key, "appSecret": self.app_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self.new_token = data["accessToken"]
        expire_in = data.get("expireIn", 7200)

        # Old token (oapi)
        resp = requests.get(
            "https://oapi.dingtalk.com/gettoken",
            params={"appkey": self.app_key, "appsecret": self.app_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self.old_token = data["access_token"]
        old_expire = data.get("expires_in", 7200)

        self.token_expires = now + min(expire_in, old_expire)

    def get_user_by_mobile(self, mobile) -> str:
        """Return userId for a given mobile number."""
        self._ensure_tokens()
        resp = requests.post(
            f"https://oapi.dingtalk.com/topapi/v2/user/getbymobile?access_token={self.old_token}",
            json={"mobile": mobile},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            raise Exception(f"getbymobile error: {data}")
        return data["result"]["userid"]

    def get_user_info(self, user_id) -> dict:
        """Return {unionId, deptId, name} for a given userId."""
        self._ensure_tokens()
        resp = requests.post(
            f"https://oapi.dingtalk.com/topapi/v2/user/get?access_token={self.old_token}",
            json={"userid": user_id, "language": "zh_CN"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            raise Exception(f"get user info error: {data}")
        result = data["result"]
        dept_list = result.get("dept_id_list", [])
        dept_id = dept_list[0] if dept_list else 0
        return {
            "unionId": result.get("unionid", ""),
            "deptId": dept_id,
            "name": result.get("name", ""),
        }

    def authorize_upload(self, user_id) -> str:
        """Return spaceId. Call BEFORE each upload to grant temporary permission."""
        self._ensure_tokens()
        resp = requests.post(
            "https://api.dingtalk.com/v1.0/workflow/processInstances/spaces/infos/query",
            headers={
                "x-acs-dingtalk-access-token": self.new_token,
                "Content-Type": "application/json",
            },
            json={"userId": user_id, "agentId": self.agent_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["result"]["spaceId"])

    def upload_file(self, file_bytes, file_name, union_id, space_id) -> dict:
        """Upload file to DingTalk storage and return {fileId, fileName, fileSize}."""
        self._ensure_tokens()
        file_size = len(file_bytes)
        headers = {
            "x-acs-dingtalk-access-token": self.new_token,
            "Content-Type": "application/json",
        }

        # Step 1: query upload info
        resp = requests.post(
            f"https://api.dingtalk.com/v1.0/storage/spaces/{space_id}/files/uploadInfos/query",
            headers=headers,
            params={"unionId": union_id},
            json={
                "protocol": "HEADER_SIGNATURE",
                "multipart": False,
                "option": {
                    "storageDriver": "DINGTALK",
                    "preCheckParam": {
                        "size": file_size,
                        "parentId": "0",
                        "name": file_name,
                    },
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        upload_key = data["uploadKey"]
        resource_url = data["headerSignatureInfo"]["resourceUrls"][0]
        oss_headers = data["headerSignatureInfo"]["headers"]

        # Step 2: PUT file to OSS
        upload_headers = dict(oss_headers)
        upload_headers["Content-Type"] = ""  # MUST be empty string
        resp = requests.put(
            resource_url,
            data=file_bytes,
            headers=upload_headers,
            timeout=60,
        )
        if resp.status_code != 200:
            raise Exception(f"OSS upload failed: {resp.status_code}")

        # Step 3: commit
        resp = requests.post(
            f"https://api.dingtalk.com/v1.0/storage/spaces/{space_id}/files/commit",
            headers=headers,
            params={"unionId": union_id},
            json={
                "uploadKey": upload_key,
                "name": file_name,
                "parentId": "0",
                "option": {
                    "size": file_size,
                    "conflictStrategy": "AUTO_RENAME",
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        dentry = resp.json()["dentry"]
        return {
            "fileId": str(dentry["id"]),
            "fileName": dentry["name"],
            "fileSize": dentry["size"],
            "spaceId": space_id,
            "fileType": dentry.get("extension", "xlsx"),
        }

    def create_approval(
        self, user_id, dept_id, title, attachments, table_rows, note=""
    ) -> str:
        """Create approval instance and return instanceId."""
        self._ensure_tokens()
        headers = {
            "x-acs-dingtalk-access-token": self.new_token,
            "Content-Type": "application/json",
        }

        attachment_value = json.dumps(
            [
                {
                    "spaceId": a["spaceId"],
                    "fileName": a["fileName"],
                    "fileSize": a["fileSize"],
                    "fileType": a["fileType"],
                    "fileId": a["fileId"],
                }
                for a in attachments
            ],
            ensure_ascii=False,
        )

        table_value = json.dumps(table_rows, ensure_ascii=False)

        form_values = [
            {"name": "标题", "value": title},
            {"name": "批量上传工资表", "value": attachment_value},
            {"name": "表格", "value": table_value},
            {"name": "备注", "value": note},
        ]

        resp = requests.post(
            "https://api.dingtalk.com/v1.0/workflow/processInstances",
            headers=headers,
            json={
                "processCode": self.process_code,
                "originatorUserId": user_id,
                "deptId": dept_id,
                "formComponentValues": form_values,
                "title": title,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("instanceId", "")


def parse_excel(file_bytes, filename):
    """
    Extract payroll data from Excel bytes.
    Returns dict with report_name, unit_name, year_month,
    transfer_total, deduction_total, net_total, tax_and_others.
    """
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return None

    # Row 1: report name (first non-empty cell)
    report_name = ""
    for cell in rows[0]:
        if cell is not None and str(cell).strip():
            report_name = str(cell).strip()
            break

    # Row 2: unit name
    unit_name = ""
    if len(rows) > 1:
        row2_text = " ".join(
            str(cell).strip() for cell in rows[1] if cell is not None
        )
        patterns = CONFIG["excel"].get("unit_name_patterns", DEFAULT_CONFIG["excel"]["unit_name_patterns"])
        matched = False
        for pattern in patterns:
            m = re.search(pattern, row2_text)
            if m:
                unit_name = m.group(1).strip()
                matched = True
                break
        if not matched:
            # Fallback: use first non-empty cell in row 2
            for cell in rows[1]:
                if cell is not None and str(cell).strip():
                    val = str(cell).strip()
                    if "名称" in val or "单位" in val:
                        unit_name = val.replace("单位", "").replace("名称", "").replace("：", "").replace(":", "").strip()
                        break

    # Year month from filename or title
    year_month = ""
    m = re.search(r"(\d{4}年\d{2}月)", filename)
    if not m:
        m = re.search(r"(\d{4}年\d{2}月)", report_name)
    if m:
        year_month = m.group(1)

    summary_marker = CONFIG["excel"].get("summary_row_marker", "合计")
    summary_row = None
    for row in rows:
        if row and str(row[0]).strip() == summary_marker:
            summary_row = row
            break

    if summary_row is None:
        return {
            "report_name": report_name,
            "unit_name": unit_name,
            "year_month": year_month,
            "transfer_total": "0.00",
            "deduction_total": "0.00",
            "net_total": "0.00",
            "tax_and_others": "0.00",
        }

    # Find column indices from header rows (rows 3-5, 0-indexed 2-4)
    header_rows = rows[2:5]

    def find_col_index(keywords, exact_first=True):
        """Find column index matching keywords in header rows."""
        # Try exact match first
        for ridx, hrow in enumerate(header_rows):
            for cidx, cell in enumerate(hrow):
                if cell is None:
                    continue
                text = str(cell).strip()
                if not text:
                    continue
                for kw in keywords:
                    if kw in text:
                        return cidx
        return -1

    excel_cols = CONFIG["excel"]["columns"]
    transfer_idx = find_col_index(excel_cols["transfer_total"]["keywords"])
    deduction_idx = find_col_index(excel_cols["deduction_total"]["keywords"])

    net_keywords = excel_cols["net_total"]["keywords"]
    net_idx = -1
    for kw in net_keywords:
        net_idx = find_col_index([kw])
        if net_idx != -1:
            break

    def get_val(idx):
        if idx >= 0 and idx < len(summary_row):
            v = summary_row[idx]
            if v is None:
                return "0.00"
            try:
                return f"{float(v):.2f}"
            except (ValueError, TypeError):
                return str(v).strip() or "0.00"
        return "0.00"

    transfer_total = get_val(transfer_idx)
    deduction_total = get_val(deduction_idx)
    net_total = get_val(net_idx)

    try:
        tax_val = float(transfer_total) - float(deduction_total) - float(net_total)
        if abs(tax_val) < 0.005:
            tax_val = 0.0
        tax_and_others = f"{tax_val:.2f}"
    except (ValueError, TypeError):
        tax_and_others = "0.00"

    return {
        "report_name": report_name,
        "unit_name": unit_name,
        "year_month": year_month,
        "transfer_total": transfer_total,
        "deduction_total": deduction_total,
        "net_total": net_total,
        "tax_and_others": tax_and_others,
    }


def generate_title(unit_names, year_month, amounts):
    """
    unit_names: list of unit names (ordered by amount desc)
    amounts: list of transfer amounts (same order)
    year_month: "2026年03月" format
    """
    n = len(unit_names)
    if n == 0:
        return f"{year_month}工资发放请示"
    if n == 1:
        return f"{unit_names[0]}{year_month}工资发放请示"
    if n == 2:
        return f"{unit_names[0]}、{unit_names[1]}{year_month}工资发放请示"
    # 3+ units
    return f"{unit_names[0]}、{unit_names[1]}等{n}家单位{year_month}工资发放请示"


def main():
    st.title("工资单上传钉钉审批")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = ""
    if "union_id" not in st.session_state:
        st.session_state.union_id = ""
    if "dept_id" not in st.session_state:
        st.session_state.dept_id = 0
    if "user_name" not in st.session_state:
        st.session_state.user_name = ""

    client = DingTalkClient(APP_KEY, APP_SECRET, AGENT_ID, PROCESS_CODE)

    # Section 1: Phone Login
    if not st.session_state.logged_in:
        st.subheader("手机号登录")
        mobile = st.text_input("手机号", value="")
        if st.button("登录"):
            if not mobile:
                st.error("请输入手机号")
                return
            try:
                user_id = client.get_user_by_mobile(mobile)
                info = client.get_user_info(user_id)
                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.union_id = info["unionId"]
                st.session_state.dept_id = info["deptId"]
                st.session_state.user_name = info["name"]
                st.success(f"登录成功：{info['name']} ({user_id})")
                st.rerun()
            except Exception as e:
                st.error(f"登录失败：{e}")
        return

    # Section 2: File Upload
    st.subheader(f"欢迎，{st.session_state.user_name}")
    col1, col2 = st.columns([1, 1])
    with col2:
        if st.button("退出登录"):
            for key in ["logged_in", "user_id", "union_id", "dept_id", "user_name"]:
                st.session_state.pop(key, None)
            st.rerun()
    uploaded_files = st.file_uploader(
        "上传工资表", type=["xlsx"], accept_multiple_files=True
    )

    if not uploaded_files:
        st.info("请上传一个或多个 Excel 工资表文件")
        return

    # Parse each file
    parsed_list = []
    for upfile in uploaded_files:
        file_bytes = upfile.read()
        upfile.seek(0)
        parsed = parse_excel(file_bytes, upfile.name)
        if parsed:
            parsed_list.append({"filename": upfile.name, **parsed})

    if not parsed_list:
        st.error("未能解析任何文件，请检查格式")
        return

    # Preview table
    st.subheader("数据预览")
    preview_data = []
    tf_columns = CONFIG["table_field"]["columns"]
    for p in parsed_list:
        row = {"文件名": p["filename"], "年月": p["year_month"]}
        for col in tf_columns:
            row[col["label"]] = p[col["key"]]
        preview_data.append(row)
    st.dataframe(preview_data)

    # Generate title
    # Sort by transfer_total desc
    sorted_items = sorted(
        parsed_list,
        key=lambda x: float(x["transfer_total"]) if x["transfer_total"] else 0,
        reverse=True,
    )
    unit_names = [p["unit_name"] for p in sorted_items]
    amounts = [p["transfer_total"] for p in sorted_items]
    year_month = sorted_items[0]["year_month"] if sorted_items else ""
    title = generate_title(unit_names, year_month, amounts)
    st.text_input("审批标题（自动生成）", value=title, disabled=True)

    # Submit button
    if st.button("提交审批"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            user_id = st.session_state.user_id
            union_id = st.session_state.union_id
            dept_id = st.session_state.dept_id

            # Upload each file to DingTalk
            attachments = []
            for i, upfile in enumerate(uploaded_files):
                status_text.text(f"正在上传：{upfile.name} ...")
                file_bytes = upfile.read()
                upfile.seek(0)

                # Authorize before EACH upload
                space_id = client.authorize_upload(user_id)
                result = client.upload_file(
                    file_bytes, upfile.name, union_id, space_id
                )
                attachments.append(result)
                progress_bar.progress((i + 1) / (len(uploaded_files) + 1))

            # Build table rows
            table_rows = []
            tf_columns = CONFIG["table_field"]["columns"]
            for p in parsed_list:
                table_rows.append(
                    [
                        {"name": col["label"], "value": p[col["key"]]}
                        for col in tf_columns
                    ]
                )

            status_text.text("正在创建审批实例...")
            instance_id = client.create_approval(
                user_id=user_id,
                dept_id=dept_id,
                title=title,
                attachments=attachments,
                table_rows=table_rows,
                note="",
            )
            progress_bar.progress(1.0)
            status_text.empty()

            if instance_id:
                st.success(f"审批创建成功！instanceId：{instance_id}")
            else:
                st.warning("审批创建完成，但未返回 instanceId")
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"提交失败：{e}")


if __name__ == "__main__":
    main()
