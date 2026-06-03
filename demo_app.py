import os
import re
import json
import time
from datetime import datetime
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
        "title_row": 1,           # 报表名所在行（1-based）
        "unit_name_row": 2,       # 单位名所在行（1-based）；0 表示无此行，单位名从标题行用正则提取
        "header_start_row": 3,    # 表头起始行（1-based）
        "header_row_count": 3,    # 表头占几行（适配多级合并表头）
        "summary_row_marker": "合计",
        "unit_name_patterns": [
            r"(?:单位名称[：:]|[名称][：:]\s*)(.+?)(?:\s|$)"
        ],
        # 从标题行提取单位名（unit_name_row=0 时启用）
        # 算法：枚举标题里每个后缀的所有出现位置，从该位置向左扩展（只接受 ALLOWED 里的字符），
        # 得到所有候选后取「最长」一个。能正确处理「...有限公司净月团餐—分公司」这种嵌套后缀。
        # title_unit_patterns 是高级正则逃生口：若配置非空，则按列表里第一个能 search 命中的 group(1) 直接返回。
        "title_unit_suffixes": [
            "有限公司", "股份公司", "分公司", "公司", "集团",
            "医院", "卫生院", "诊所",
            "研究院", "研究所", "学院", "大学", "学校",
            "中心", "管委会", "事业部", "处", "局"
        ],
        "title_unit_allowed_chars": r"[一-龥A-Za-z0-9（）()·\-—]",
        "title_unit_patterns": [],
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
    },
    "ui": {
        "template_name": "工资发放审批",
        "description": "请上传 Excel 工资表，系统将自动解析数据并提交钉钉 OA 审批流程。"
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


def _extract_year_month(text, current_year=None):
    """
    从一段文本里抽取「YYYY年MM月」并归一化为 4位年+2位月 字符串。

    支持的形态（按从严到宽顺序）：
      1) 4位年+1或2位月，连体：  2026年5月  / 2026年05月
      2) 2位年+1或2位月，连体：  26年5月
      3) 分离形态：先找最右一个「YYYY年」或「YY年」，再在其后找最近的「N月」
         例：「...2026年派遣员工5月工资明细表」

    2 位年归一化规则：>= (current_year-50) 的两位数算 21 世纪，否则算 20 世纪。
    匹配不到返回 ""。
    """
    if not text:
        return ""
    if current_year is None:
        current_year = datetime.now().year

    def normalize(y, mo):
        y = int(y); mo = int(mo)
        if y < 100:
            # 2 位年补全：在 [current-50, current+49] 范围里选
            century_base = (current_year // 100) * 100  # 2000
            cand_new = century_base + y                 # 2026
            cand_old = cand_new - 100                   # 1926
            # 选离当前年最近、且距离 < 50 的那个
            if abs(cand_new - current_year) < 50:
                y = cand_new
            else:
                y = cand_old
        if not (1 <= mo <= 12):
            return ""
        return f"{y:04d}年{mo:02d}月"

    # 规则 1：4 位年连体
    m = re.search(r"(\d{4})年(\d{1,2})月", text)
    if m:
        out = normalize(m.group(1), m.group(2))
        if out:
            return out

    # 规则 2：2 位年连体（注意要求年前面不是数字，避免吃掉 4 位年的尾巴）
    m = re.search(r"(?<!\d)(\d{2})年(\d{1,2})月", text)
    if m:
        out = normalize(m.group(1), m.group(2))
        if out:
            return out

    # 规则 3：分离形态——先找最后一个 N年，再在其后找 N月
    year_match = None
    for ym in re.finditer(r"(?<!\d)(\d{4}|\d{2})年", text):
        year_match = ym
    if year_match:
        tail = text[year_match.end():]
        mo_match = re.search(r"(\d{1,2})月", tail)
        if mo_match:
            out = normalize(year_match.group(1), mo_match.group(1))
            if out:
                return out
    return ""


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

    excel_cfg = CONFIG.get("excel", DEFAULT_CONFIG["excel"])
    default_excel = DEFAULT_CONFIG["excel"]
    title_row_idx = int(excel_cfg.get("title_row", default_excel["title_row"])) - 1
    unit_name_row_cfg = int(excel_cfg.get("unit_name_row", default_excel["unit_name_row"]))
    header_start_idx = int(excel_cfg.get("header_start_row", default_excel["header_start_row"])) - 1
    header_row_count = int(excel_cfg.get("header_row_count", default_excel["header_row_count"]))

    # Title row: report name (first non-empty cell)
    report_name = ""
    if 0 <= title_row_idx < len(rows):
        for cell in rows[title_row_idx]:
            if cell is not None and str(cell).strip():
                report_name = str(cell).strip()
                break

    patterns = excel_cfg.get("unit_name_patterns", default_excel["unit_name_patterns"])
    title_patterns = excel_cfg.get("title_unit_patterns", default_excel["title_unit_patterns"])
    title_suffixes = excel_cfg.get("title_unit_suffixes", default_excel["title_unit_suffixes"])
    title_allowed = excel_cfg.get("title_unit_allowed_chars", default_excel["title_unit_allowed_chars"])

    # Unit name: from unit_name_row if configured, else extract from title row
    unit_name = ""
    if unit_name_row_cfg > 0:
        unit_row_idx = unit_name_row_cfg - 1
        if 0 <= unit_row_idx < len(rows):
            row_text = " ".join(
                str(cell).strip() for cell in rows[unit_row_idx] if cell is not None
            )
            matched = False
            for pattern in patterns:
                m = re.search(pattern, row_text)
                if m:
                    unit_name = m.group(1).strip()
                    matched = True
                    break
            if not matched:
                # Fallback: use first non-empty cell in that row
                for cell in rows[unit_row_idx]:
                    if cell is not None and str(cell).strip():
                        val = str(cell).strip()
                        if "名称" in val or "单位" in val:
                            unit_name = val.replace("单位", "").replace("名称", "").replace("：", "").replace(":", "").strip()
                            break
    else:
        # No dedicated unit row → extract from title row
        # 1) 高级用户可通过 title_unit_patterns 提供自定义正则（取第一个命中的 group 1）
        if title_patterns:
            for pattern in title_patterns:
                try:
                    m = re.search(pattern, report_name)
                except re.error:
                    continue
                if m and m.lastindex:
                    unit_name = m.group(1).strip()
                    break
        # 2) 否则用「后缀枚举 + 向左贪婪扩展 + 取最长」算法
        if not unit_name and title_suffixes:
            try:
                allowed_re = re.compile(title_allowed)
            except re.error:
                allowed_re = None
            if allowed_re is not None:
                candidates = []
                for suf in title_suffixes:
                    for m in re.finditer(re.escape(suf), report_name):
                        start = m.start()
                        while start > 0 and allowed_re.fullmatch(report_name[start - 1]):
                            start -= 1
                        cand = report_name[start : m.end()].strip()
                        if cand:
                            candidates.append(cand)
                if candidates:
                    unit_name = max(candidates, key=len)

    # Year month: 优先取标题（审计权威来源），文件名作为兜底
    # 同时单独保留两路结果，供 UI 做「标题 vs 文件名」一致性提醒
    year_month_from_title = _extract_year_month(report_name)
    year_month_from_filename = _extract_year_month(filename)
    year_month = year_month_from_title or year_month_from_filename

    summary_marker = excel_cfg.get("summary_row_marker", default_excel["summary_row_marker"])
    # Strip ALL whitespace (incl. internal) to tolerate variants like "合 计" / " 合计 "
    marker_normalized = re.sub(r"\s+", "", summary_marker)
    summary_row = None
    for row in rows:
        if row and row[0] is not None:
            first_cell = re.sub(r"\s+", "", str(row[0]))
            if first_cell == marker_normalized:
                summary_row = row
                break

    if summary_row is None:
        return {
            "report_name": report_name,
            "unit_name": unit_name,
            "year_month": year_month,
            "year_month_from_title": year_month_from_title,
            "year_month_from_filename": year_month_from_filename,
            "transfer_total": "0.00",
            "deduction_total": "0.00",
            "net_total": "0.00",
            "tax_and_others": "0.00",
        }

    # Header rows from config (1-based start, N rows)
    header_rows = rows[header_start_idx : header_start_idx + header_row_count]

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

    excel_cols = excel_cfg["columns"]
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
        "year_month_from_title": year_month_from_title,
        "year_month_from_filename": year_month_from_filename,
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
    ui_config = CONFIG.get("ui", DEFAULT_CONFIG["ui"])
    template_name = ui_config.get("template_name", "工资发放审批")
    description = ui_config.get("description", "")

    st.title(f"📋 {template_name}")
    if description:
        st.info(description)

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

    # 标题 vs 文件名年月一致性检查（取标题为准；不一致时提醒制表人核对）
    for p in parsed_list:
        t = p.get("year_month_from_title", "")
        f = p.get("year_month_from_filename", "")
        if t and f and t != f:
            st.warning(
                f"⚠️ {p['filename']}：标题中年月「{t}」与文件名年月「{f}」不一致，"
                f"已以**标题**为准。请确认报表标题是否需要更正。"
            )
        elif not t and f:
            st.warning(
                f"⚠️ {p['filename']}：报表标题中未识别到年月，已退回使用文件名年月「{f}」。"
                f"建议在标题中明确写出年月。"
            )

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
