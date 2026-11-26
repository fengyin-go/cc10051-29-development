"""质量报告钻取、重检清单、输入版本与规则重跑的内存领域工作流。

这里刻意把“命中理由”和“重检事项”分开：
- 一条记录可以同时命中多个维度，因此有多条 hit/reason；
- 重检清单按原报告 + 实体记录去重，同一行只预约一次；
- 原报告输入快照不覆盖，迟到的清洗输入作为新版本参与新一轮重跑。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.store import store

ENTITY_CODE = "CUSTOMER"
ENTITY_NAME = "客户主数据"
ORIG_REPORT_ID = 2601
ORIG_INPUT_ID = 2601
LATE_INPUT_ID = 2602
PHONE_RULE_ID = 2601
EMAIL_RULE_ID = 2602
ITEM_ID = 2601
BATCH_ID = 2601

ORIG_BATCH = "QR-20261126-CUST-R1"
ROUND_ONE = "R1"
RECHECK_BATCH = "RCB-QR2601-01"
RECORD_X = "X"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_id(value: Any) -> str:
    return str("" if value is None else value).strip()


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


class QualityWorkflow:
    """质量复查工作流状态。

    重检主条目放入 store 的 ``quality_recheck`` 表，使其同时可被通用资源
    接口查询；命中来源、输入快照和批次汇总由本对象保存完整结构。
    """

    def __init__(self) -> None:
        self.ready = False
        self.inputs: list[dict[str, Any]] = []
        self.pending_late_input: dict[str, Any] | None = None
        self.hits: list[dict[str, Any]] = []
        self.batches: list[dict[str, Any]] = []
        self.rule_links: list[dict[str, Any]] = []
        self._seed()

    def ensure(self) -> None:
        """供应用启动/服务注册时显式确保种子场景已装载。"""
        self._seed()

    # ------------------------------------------------------------------
    # 种子场景：X 在原报告中缺少手机号、邮箱两项；之后手机号被迟到输入补齐。
    # ------------------------------------------------------------------
    def _seed(self) -> None:
        if self.ready:
            return
        self.ready = True
        self._seed_rules()
        self._seed_report()
        self._seed_inputs_and_hits()
        self._seed_recheck()

    def _seed_rules(self) -> None:
        rules = store.rows("quality_rule")
        if not store.find("quality_rule", PHONE_RULE_ID):
            rules.insert(0, {
                "id": PHONE_RULE_ID,
                "status": "已启用",
                "pending": False,
                "abnormal": True,
                "规则名称": "客户手机号非空校验",
                "实体编码": ENTITY_CODE,
                "检查维度": "手机号完整性",
                "阈值口径": "手机号非空，且符合11位大陆手机号口径",
                "严重级别": "高",
                "rule_code": "RULE_CUST_PHONE_REQUIRED",
                "target_field": "手机号",
                "standard_code": "QSTD-CUST-PHONE-v2",
                "standard_name": "客户手机号完整性检查标准 v2",
                "rule_standard": "QSTD-CUST-PHONE-v2《客户手机号完整性检查标准》：清洗后手机号不得为空",
                "expression": "trim(coalesce(手机号, '')) <> ''",
            })
        if not store.find("quality_rule", EMAIL_RULE_ID):
            rules.insert(1 if rules else 0, {
                "id": EMAIL_RULE_ID,
                "status": "已启用",
                "pending": False,
                "abnormal": True,
                "规则名称": "客户邮箱非空校验",
                "实体编码": ENTITY_CODE,
                "检查维度": "邮箱完整性",
                "阈值口径": "邮箱非空，且包含 @ 与域名",
                "严重级别": "高",
                "rule_code": "RULE_CUST_EMAIL_REQUIRED",
                "target_field": "邮箱",
                "standard_code": "QSTD-CUST-EMAIL-v3",
                "standard_name": "客户邮箱完整性检查标准 v3",
                "rule_standard": "QSTD-CUST-EMAIL-v3《客户邮箱完整性检查标准》：清洗后邮箱不得为空",
                "expression": "trim(coalesce(邮箱, '')) <> ''",
            })

    def _seed_report(self) -> None:
        if store.find("quality_result", ORIG_REPORT_ID):
            return
        reports = store.rows("quality_result")
        reports.insert(0, {
            "id": ORIG_REPORT_ID,
            "status": "已生成",
            "pending": False,
            "abnormal": True,
            "报告批次": ORIG_BATCH,
            "report_code": ORIG_BATCH,
            "实体编码": ENTITY_CODE,
            "entity_code": ENTITY_CODE,
            "实体名称": ENTITY_NAME,
            "检查总数": "6",
            "命中数": "2",
            "受影响记录数": "1",
            "评分结果": "66.67%",
            "报告轮次": ROUND_ONE,
            "round": ROUND_ONE,
            "round_number": 1,
            "root_report_id": ORIG_REPORT_ID,
            "检查维度": "手机号完整性、邮箱完整性",
            "输入批次": "CLEAN-20261126-ORIG",
            "实际输入ID": "QIN-CUST-ORIG",
            "generated_at": "2026-11-26T09:05:00+00:00",
            "summary": "3 行客户输入 × 2 项完整性规则 = 6 项检查；X 命中 2 项，形成 1 条待查记录。",
        })

    def _original_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "记录编号": RECORD_X,
                "record_id": RECORD_X,
                "客户名称": "X",
                "手机号": "",
                "邮箱": "",
                "证件号": "ID-X-0001",
                "数据凭据": "CRED-ORIG-X-0900",
                "清洗批次": "CLEAN-20261126-ORIG",
            },
            {
                "记录编号": "W",
                "record_id": "W",
                "客户名称": "W",
                "手机号": "13900001111",
                "邮箱": "w@example.com",
                "证件号": "ID-W-0002",
                "数据凭据": "CRED-ORIG-W-0900",
                "清洗批次": "CLEAN-20261126-ORIG",
            },
            {
                "记录编号": "Z",
                "record_id": "Z",
                "客户名称": "Z",
                "手机号": "13700002222",
                "邮箱": "z@example.com",
                "证件号": "ID-Z-0003",
                "数据凭据": "CRED-ORIG-Z-0900",
                "清洗批次": "CLEAN-20261126-ORIG",
            },
        ]

    def _seed_inputs_and_hits(self) -> None:
        orig_rows = self._original_rows()
        self.inputs = [{
            "id": ORIG_INPUT_ID,
            "input_code": "QIN-CUST-ORIG",
            "输入批次": "CLEAN-20261126-ORIG",
            "version": "R1-original",
            "label": "原报告实际输入",
            "kind": "cleanse_output_rows",
            "实体编码": ENTITY_CODE,
            "entity_code": ENTITY_CODE,
            "source_credential": "CRED-ORIG-X-0900",
            "received_at": "2026-11-26T09:00:00+00:00",
            "is_late": False,
            "row_count": len(orig_rows),
            "rows": orig_rows,
            "note": "生成原质量报告时规则实际读取的清洗输出快照，不以规则名称代替输入。",
        }]
        # 迟到输入先作为待送达事件保存；调用送达接口或第一次刷新时才进入可用输入列表，
        # 这样刷新前仍可核对“两项理由”的原始状态。
        self.pending_late_input = self._build_late_input()
        x_row = orig_rows[0]
        self.hits = [
            {
                "id": 9101,
                "hit_code": "HIT-QR2601-X-PHONE",
                "report_id": ORIG_REPORT_ID,
                "report_batch": ORIG_BATCH,
                "round": ROUND_ONE,
                "entity_code": ENTITY_CODE,
                "record_id": RECORD_X,
                "record_label": "X",
                "rule_id": PHONE_RULE_ID,
                "rule_code": "RULE_CUST_PHONE_REQUIRED",
                "rule_name": "客户手机号非空校验",
                "dimension": "手机号完整性",
                "field": "手机号",
                "standard_code": "QSTD-CUST-PHONE-v2",
                "rule_standard": "QSTD-CUST-PHONE-v2《客户手机号完整性检查标准》",
                "input_id": "QIN-CUST-ORIG",
                "actual_value": "",
                "reason": "手机号为空，缺少必填字段「手机号」",
                "original_row": deepcopy(x_row),
            },
            {
                "id": 9102,
                "hit_code": "HIT-QR2601-X-EMAIL",
                "report_id": ORIG_REPORT_ID,
                "report_batch": ORIG_BATCH,
                "round": ROUND_ONE,
                "entity_code": ENTITY_CODE,
                "record_id": RECORD_X,
                "record_label": "X",
                "rule_id": EMAIL_RULE_ID,
                "rule_code": "RULE_CUST_EMAIL_REQUIRED",
                "rule_name": "客户邮箱非空校验",
                "dimension": "邮箱完整性",
                "field": "邮箱",
                "standard_code": "QSTD-CUST-EMAIL-v3",
                "rule_standard": "QSTD-CUST-EMAIL-v3《客户邮箱完整性检查标准》",
                "input_id": "QIN-CUST-ORIG",
                "actual_value": "",
                "reason": "邮箱为空，缺少必填字段「邮箱」",
                "original_row": deepcopy(x_row),
            },
        ]
        self.batches = [{
            "id": BATCH_ID,
            "batch_code": RECHECK_BATCH,
            "重检批次": RECHECK_BATCH,
            "report_id": ORIG_REPORT_ID,
            "原报告批次": ORIG_BATCH,
            "report_round": ROUND_ONE,
            "报告轮次": ROUND_ONE,
            "entity_code": ENTITY_CODE,
            "实体编码": ENTITY_CODE,
            "check_total": 2,
            "检查总数": 2,
            "list_total": 1,
            "清单总数": 1,
            "work_count": 1,
            "重检事项数": 1,
            "item_count": 1,
            "rule_check_total": 2,
            "规则检查项总数": 2,
            "reason_count": 2,
            "命中理由数": 2,
            "status": "处理中",
            "created_at": "2026-11-26T09:06:00+00:00",
        }]

    def _seed_recheck(self) -> None:
        if store.find("quality_recheck", ITEM_ID):
            return
        items = store.rows("quality_recheck")
        items.insert(0, {
            "id": ITEM_ID,
            "status": "处理中",
            "pending": True,
            "abnormal": True,
            "重检单号": "RC-X-2601",
            "recheck_code": "RC-X-2601",
            "重检批次": RECHECK_BATCH,
            "batch_code": RECHECK_BATCH,
            "原报告ID": ORIG_REPORT_ID,
            "report_id": ORIG_REPORT_ID,
            "原报告批次": ORIG_BATCH,
            "report_batch": ORIG_BATCH,
            "root_report_id": ORIG_REPORT_ID,
            "报告轮次": ROUND_ONE,
            "report_round": ROUND_ONE,
            "round": ROUND_ONE,
            "实体编码": ENTITY_CODE,
            "entity_code": ENTITY_CODE,
            "实体名称": ENTITY_NAME,
            "记录编号": RECORD_X,
            "record_id": RECORD_X,
            "记录名称": "X",
            "record_label": "X",
            "命中维度": "手机号完整性、邮箱完整性",
            "reason_ids": [9101, 9102],
            "original_reason_count": 2,
            "原始理由数": 2,
            "current_reason_count": 2,
            "当前理由数": 2,
            "复查员": "复查员",
            "assignee": "复查员",
            "claimed": True,
            "claimed_at": "2026-11-26T09:10:00+00:00",
            "预约次数": 1,
            "reservation_count": 1,
            "effective_input_id": "QIN-CUST-ORIG",
            "adopted_input_id": "QIN-CUST-ORIG",
            "input_conflict": False,
            "conflict_message": "",
            "disposition_scope": "仅预约并处置原报告 QR-20261126-CUST-R1 中实体 CUSTOMER 的记录 X；重跑手机号、邮箱两项规则标准，不把规则名称当作整份输入。",
            "处置范围": "仅处置 X 的手机号与邮箱检查，不扩大为整份输入或其他实体。",
            "created_at": "2026-11-26T09:06:00+00:00",
        })

    # ------------------------------------------------------------------
    # 解析与序列化
    # ------------------------------------------------------------------
    def find_report(self, ref: Any) -> dict[str, Any] | None:
        rid = _as_int(ref)
        if rid is not None:
            row = store.find("quality_result", rid)
            if row:
                return row
        text = _norm_id(ref)
        for row in store.rows("quality_result"):
            if text in {_norm_id(row.get("id")), _norm_id(row.get("报告批次")),
                        _norm_id(row.get("report_code"))}:
                return row
        return None

    def find_item(self, ref: Any) -> dict[str, Any] | None:
        iid = _as_int(ref)
        if iid is not None:
            row = store.find("quality_recheck", iid)
            if row:
                return row
        text = _norm_id(ref)
        for row in store.rows("quality_recheck"):
            if text in {_norm_id(row.get("id")), _norm_id(row.get("重检单号")),
                        _norm_id(row.get("recheck_code"))}:
                return row
        return None

    def find_rule(self, ref: Any) -> dict[str, Any] | None:
        rid = _as_int(ref)
        if rid is not None:
            row = store.find("quality_rule", rid)
            if row:
                return row
        text = _norm_id(ref)
        for row in store.rows("quality_rule"):
            if text in {_norm_id(row.get("id")), _norm_id(row.get("rule_code")),
                        _norm_id(row.get("规则名称"))}:
                return row
        return None

    def find_input(self, ref: Any) -> dict[str, Any] | None:
        text = _norm_id(ref)
        iid = _as_int(ref)
        for data in self.inputs:
            if iid is not None and int(data.get("id", -1)) == iid:
                return data
            if text in {_norm_id(data.get("id")), _norm_id(data.get("input_code")),
                        _norm_id(data.get("输入批次")), _norm_id(data.get("version"))}:
                return data
        return None

    def hits_for_report(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        rid = report.get("id")
        batch = report.get("报告批次")
        return [deepcopy(hit) for hit in self.hits
                if hit.get("report_id") == rid or hit.get("report_batch") == batch]

    def reasons_for_item(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        ids = {_norm_id(value) for value in item.get("reason_ids", [])}
        return [deepcopy(hit) for hit in self.hits if _norm_id(hit.get("id")) in ids]

    def batch_for_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        code = item.get("batch_code") or item.get("重检批次")
        for batch in self.batches:
            if batch.get("batch_code") == code or batch.get("重检批次") == code:
                return deepcopy(batch)
        return None

    def inputs_for_entity(self, entity_code: str) -> list[dict[str, Any]]:
        return [deepcopy(data) for data in self.inputs
                if data.get("entity_code") == entity_code or data.get("实体编码") == entity_code]

    def latest_input(self, entity_code: str) -> dict[str, Any] | None:
        candidates = [data for data in self.inputs
                      if data.get("entity_code") == entity_code or data.get("实体编码") == entity_code]
        if not candidates:
            return None
        return deepcopy(sorted(candidates, key=lambda x: (x.get("received_at", ""), x.get("id", 0)))[-1])

    def _input_summary(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not data:
            return None
        return {key: value for key, value in data.items() if key != "rows"}

    def serialize_item(
        self,
        item: dict[str, Any],
        *,
        include_evaluation: bool = True,
        include_all_inputs: bool = True,
    ) -> dict[str, Any]:
        data = deepcopy(item)
        reasons = self.reasons_for_item(item)
        data["original_reasons"] = reasons
        data["reasons"] = reasons
        data["reason_count"] = len(reasons)
        data["原始理由数"] = len(reasons)
        data["batch"] = self.batch_for_item(item)

        entity_code = _norm_id(item.get("entity_code") or item.get("实体编码"))
        effective = self.find_input(item.get("effective_input_id") or item.get("adopted_input_id"))
        if effective is None:
            effective = self.latest_input(entity_code)
        data["effective_input"] = deepcopy(effective)
        data["实际使用的输入"] = deepcopy(effective)
        if include_all_inputs:
            data["available_inputs"] = self.inputs_for_entity(entity_code)
        if include_evaluation and effective is not None:
            data["current_run"] = self.evaluate_item(item, effective.get("input_code"))
            data["当前试算结果"] = data["current_run"]
        return data

    # ------------------------------------------------------------------
    # 报告钻取
    # ------------------------------------------------------------------
    def report_drilldown(self, report_ref: Any) -> dict[str, Any] | None:
        report = self.find_report(report_ref)
        if report is None:
            return None
        hits = self.hits_for_report(report)
        records: dict[str, dict[str, Any]] = {}
        for hit in hits:
            rid = hit["record_id"]
            bucket = records.setdefault(rid, {
                "record_id": rid,
                "record_label": hit.get("record_label", rid),
                "original_row": hit.get("original_row", {}),
                "reasons": [],
                "reason_ids": [],
                "dimensions": [],
                "scheduled": False,
                "recheck_item_id": None,
                "recheck_code": None,
                "recheck_status": None,
            })
            bucket["reasons"].append(hit)
            bucket["reason_ids"].append(hit["id"])
            bucket["dimensions"].append(hit["dimension"])

        for item in store.rows("quality_recheck"):
            if item.get("report_id") != report.get("id"):
                continue
            rid = _norm_id(item.get("record_id") or item.get("记录编号"))
            if rid in records:
                records[rid]["scheduled"] = True
                records[rid]["recheck_item_id"] = item.get("id")
                records[rid]["recheck_code"] = item.get("recheck_code") or item.get("重检单号")
                records[rid]["recheck_status"] = item.get("status")

        record_rows = list(records.values())
        dimensions: dict[str, dict[str, Any]] = {}
        for hit in hits:
            dim = hit["dimension"]
            card = dimensions.setdefault(dim, {
                "dimension": dim,
                "rule_id": hit["rule_id"],
                "rule_name": hit["rule_name"],
                "standard_code": hit["standard_code"],
                "rule_standard": hit["rule_standard"],
                "hit_count": 0,
                "records": [],
            })
            card["hit_count"] += 1
            card["records"].append(hit["record_id"])

        active_items = [item for item in store.rows("quality_recheck")
                        if item.get("report_id") == report.get("id") and item.get("status") != "已完成"]
        return {
            "ok": True,
            "report": deepcopy(report),
            "original_input": self.find_input(report.get("实际输入ID")),
            "dimensions": list(dimensions.values()),
            "hit_sources": hits,
            "actual_hits": hits,
            "records": record_rows,
            "pending_rows": [row for row in record_rows
                             if not row["scheduled"] or row["recheck_status"] != "已完成"],
            "totals": {
                "check_total": int(report.get("检查总数", 0) or 0),
                "hit_count": len(hits),
                "affected_record_count": len(record_rows),
                "pending_row_count": len(record_rows),
                "recheck_item_count": len(active_items),
            },
        }

    def report_detail(self, report_ref: Any) -> dict[str, Any] | None:
        report = self.find_report(report_ref)
        if report is None:
            return None
        drilldown = self.report_drilldown(report_ref)
        root_id = report.get("root_report_id") or report.get("id")
        rounds = [deepcopy(row) for row in store.rows("quality_result")
                  if row.get("root_report_id") == root_id]
        rounds.sort(key=lambda row: row.get("round_number", 1))
        items = [self.serialize_item(item) for item in store.rows("quality_recheck")
                 if item.get("root_report_id") == root_id or item.get("report_id") == report.get("id")]
        return {
            "ok": True,
            "report": deepcopy(report),
            "original_hits": drilldown["hit_sources"] if drilldown else [],
            "rounds": rounds,
            "recheck_items": items,
            "original_input": drilldown["original_input"] if drilldown else None,
        }

    # ------------------------------------------------------------------
    # 发起重检：按原报告 + 记录去重，理由可以多项，工作只预约一次。
    # ------------------------------------------------------------------
    def create_rechecks(
        self,
        report_ref: Any,
        *,
        hit_ids: list[Any] | None = None,
        record_ids: list[Any] | None = None,
        reviewer: str = "",
    ) -> dict[str, Any]:
        report = self.find_report(report_ref)
        if report is None:
            return {"ok": False, "status_code": 404, "message": "原质量报告不存在，无法按报告身份生成重检清单"}

        report_hits = self.hits_for_report(report)
        selected_hits = self._select_hits(report_hits, hit_ids=hit_ids, record_ids=record_ids)
        if not selected_hits:
            return {"ok": False, "message": "请先勾选至少一个实际命中来源或待查行"}

        by_record: dict[str, list[dict[str, Any]]] = {}
        for hit in selected_hits:
            by_record.setdefault(hit["record_id"], []).append(hit)

        batch = self._batch_for_report(report, create=True)
        assert batch is not None
        items = store.rows("quality_recheck")
        created: list[dict[str, Any]] = []
        reused: list[dict[str, Any]] = []

        for record_id, record_hits in by_record.items():
            reason_ids = [hit["id"] for hit in record_hits]
            existing = next((item for item in items
                             if item.get("report_id") == report.get("id")
                             and _norm_id(item.get("record_id")) == _norm_id(record_id)), None)
            if existing is not None:
                merged = list(dict.fromkeys([*(existing.get("reason_ids", [])), *reason_ids]))
                existing["reason_ids"] = merged
                existing["reservation_count"] = 1
                existing["预约次数"] = 1
                reused.append(existing)
                continue

            next_id = max((int(row.get("id", 0) or 0) for row in items), default=2600) + 1
            code = f"RC-{report.get('id')}-{next_id}"
            dimensions = "、".join(dict.fromkeys(hit["dimension"] for hit in record_hits))
            item = {
                "id": next_id,
                "status": "待领取",
                "pending": True,
                "abnormal": True,
                "重检单号": code,
                "recheck_code": code,
                "重检批次": batch["batch_code"],
                "batch_code": batch["batch_code"],
                "原报告ID": report.get("id"),
                "report_id": report.get("id"),
                "原报告批次": report.get("报告批次"),
                "report_batch": report.get("报告批次"),
                "root_report_id": report.get("root_report_id") or report.get("id"),
                "报告轮次": report.get("报告轮次") or report.get("round") or "R1",
                "report_round": report.get("报告轮次") or report.get("round") or "R1",
                "round": report.get("报告轮次") or report.get("round") or "R1",
                "实体编码": report.get("实体编码"),
                "entity_code": report.get("entity_code") or report.get("实体编码"),
                "实体名称": report.get("实体名称", ""),
                "记录编号": record_id,
                "record_id": record_id,
                "记录名称": record_hits[0].get("record_label", record_id),
                "record_label": record_hits[0].get("record_label", record_id),
                "命中维度": dimensions,
                "reason_ids": reason_ids,
                "original_reason_count": len(reason_ids),
                "原始理由数": len(reason_ids),
                "current_reason_count": len(reason_ids),
                "当前理由数": len(reason_ids),
                "复查员": reviewer,
                "assignee": reviewer,
                "claimed": bool(reviewer),
                "预约次数": 1,
                "reservation_count": 1,
                "effective_input_id": report.get("实际输入ID"),
                "adopted_input_id": report.get("实际输入ID"),
                "input_conflict": False,
                "conflict_message": "",
                "disposition_scope": f"仅处置原报告 {report.get('报告批次')} 中实体 {report.get('实体编码')} 的记录 {record_id} 及其勾选维度。",
                "处置范围": "按所选记录和维度处置，不把不合格条目所属规则名称当作整份输入。",
                "created_at": now_iso(),
            }
            items.append(item)
            created.append(item)

        self._recalc_batch(batch)
        return {
            "ok": True,
            "message": f"重检确认完成：{len(by_record)} 条记录只生成/复用 {len(by_record)} 笔重检，未按 {len(selected_hits)} 项理由拆单",
            "batch": deepcopy(batch),
            "items": [self.serialize_item(item) for item in [*created, *reused]],
            "created_count": len(created),
            "reused_count": len(reused),
            "selected_reason_count": len(selected_hits),
            "duplicate_record_count": 0,
        }

    def _select_hits(
        self,
        report_hits: list[dict[str, Any]],
        *,
        hit_ids: list[Any] | None,
        record_ids: list[Any] | None,
    ) -> list[dict[str, Any]]:
        if hit_ids:
            wanted = {_norm_id(value) for value in hit_ids}
            selected = [hit for hit in report_hits if _norm_id(hit.get("id")) in wanted
                        or _norm_id(hit.get("hit_code")) in wanted]
            if selected:
                return selected
        if record_ids:
            wanted_records = {_norm_id(value) for value in record_ids}
            return [hit for hit in report_hits if _norm_id(hit.get("record_id")) in wanted_records]
        return report_hits

    def _batch_for_report(self, report: dict[str, Any], *, create: bool) -> dict[str, Any] | None:
        code = f"RCB-{report.get('id')}-01"
        for batch in self.batches:
            if batch.get("report_id") == report.get("id"):
                return batch
        if not create:
            return None
        batch = {
            "id": max((int(b.get("id", 0)) for b in self.batches), default=BATCH_ID) + 1,
            "batch_code": code,
            "重检批次": code,
            "report_id": report.get("id"),
            "原报告批次": report.get("报告批次"),
            "report_round": report.get("报告轮次") or "R1",
            "报告轮次": report.get("报告轮次") or "R1",
            "entity_code": report.get("实体编码"),
            "实体编码": report.get("实体编码"),
            "check_total": 0,
            "检查总数": 0,
            "work_count": 0,
            "重检事项数": 0,
            "item_count": 0,
            "reason_count": 0,
            "命中理由数": 0,
            "status": "待领取",
            "created_at": now_iso(),
        }
        self.batches.append(batch)
        return batch

    def _recalc_batch(self, batch: dict[str, Any]) -> None:
        code = batch.get("batch_code")
        items = [item for item in store.rows("quality_recheck") if item.get("batch_code") == code]
        reason_count = sum(len(item.get("reason_ids", [])) for item in items)
        completed = sum(1 for item in items if item.get("status") == "已完成")
        batch["item_count"] = len(items)
        batch["work_count"] = len(items)
        batch["list_total"] = len(items)
        batch["清单总数"] = len(items)
        batch["重检事项数"] = len(items)
        batch["rule_check_total"] = reason_count
        batch["规则检查项总数"] = reason_count
        batch["check_total"] = reason_count
        batch["检查总数"] = reason_count
        batch["reason_count"] = reason_count
        batch["命中理由数"] = reason_count
        if items and completed == len(items):
            batch["status"] = "已完成"
        elif any(item.get("status") == "处理中" for item in items):
            batch["status"] = "处理中"

    # ------------------------------------------------------------------
    # 列表、领取、迟到输入与刷新
    # ------------------------------------------------------------------
    def list_rechecks(
        self,
        *,
        entity_code: str = "",
        report_round: str = "",
        status: str = "",
        batch_code: str = "",
        keyword: str = "",
    ) -> dict[str, Any]:
        items = list(store.rows("quality_recheck"))
        if entity_code:
            items = [item for item in items
                     if entity_code.casefold() in _norm_id(item.get("entity_code") or item.get("实体编码")).casefold()]
        if report_round:
            items = [item for item in items
                     if report_round.casefold() in _norm_id(item.get("report_round") or item.get("报告轮次")).casefold()]
        if status:
            items = [item for item in items if item.get("status") == status]
        if batch_code:
            items = [item for item in items
                     if batch_code.casefold() in _norm_id(item.get("batch_code") or item.get("重检批次")).casefold()]
        if keyword:
            needle = keyword.casefold()
            items = [item for item in items if needle in " ".join([
                _norm_id(item.get("记录编号")), _norm_id(item.get("record_id")),
                _norm_id(item.get("记录名称")), _norm_id(item.get("命中维度")),
                _norm_id(item.get("重检单号")), _norm_id(item.get("原报告批次")),
            ]).casefold()]
        serialized = [self.serialize_item(item) for item in items]
        return {
            "ok": True,
            "items": serialized,
            "total": len(serialized),
            "page": 1,
            "size": max(len(serialized), 1),
            "batches": deepcopy(self.batches),
            "totals": {
                "item_count": len(serialized),
                "record_count": len({item.get("record_id") for item in serialized}),
                "reason_count": sum(item.get("reason_count", 0) for item in serialized),
            },
        }

    def claim(self, item_ref: Any, reviewer: str = "复查员") -> dict[str, Any]:
        item = self.find_item(item_ref)
        if item is None:
            return {"ok": False, "status_code": 404, "message": "重检清单不存在"}
        if item.get("status") == "已完成":
            return {"ok": False, "message": "该条重检已办结，不能重复领取"}
        item["status"] = "处理中"
        item["pending"] = True
        item["claimed"] = True
        item["assignee"] = reviewer or "复查员"
        item["复查员"] = item["assignee"]
        item["claimed_at"] = item.get("claimed_at") or now_iso()
        # 无论刷新/重复领取多少次，预约次数始终为 1。
        item["reservation_count"] = 1
        item["预约次数"] = 1
        batch = self.batch_for_item(item)
        if batch:
            batch["status"] = "处理中"
        return {"ok": True, "message": "已领取，可在刷新输入冲突后继续办理该条重检",
                "item": self.serialize_item(item)}

    def _build_late_input(self, entity_code: str = ENTITY_CODE) -> dict[str, Any]:
        late_rows = self._original_rows()
        x_row = next(row for row in late_rows if row["record_id"] == RECORD_X)
        x_row["手机号"] = "13800138000"
        x_row["数据凭据"] = "CRED-LATE-X-1030"
        x_row["清洗批次"] = "CLEAN-20261126-LATE"
        return {
            "id": LATE_INPUT_ID,
            "input_code": "QIN-CUST-LATE-R2",
            "输入批次": "CLEAN-20261126-LATE",
            "version": "R2-late",
            "label": "迟到后到清洗输入",
            "kind": "cleanse_output_rows",
            "实体编码": entity_code,
            "entity_code": entity_code,
            "source_credential": "CRED-LATE-X-1030",
            "received_at": "2026-11-26T10:30:00+00:00",
            "is_late": True,
            "row_count": len(late_rows),
            "rows": late_rows,
            "note": "复查员领取后迟到；源系统补传手机号，清洗后 X 的手机号已有值，邮箱仍缺失。",
        }

    def arrive_late_input(self, entity_code: str = ENTITY_CODE) -> dict[str, Any]:
        existing = next((data for data in self.inputs if data.get("is_late")
                         and data.get("entity_code") == entity_code), None)
        if existing is not None:
            return {"ok": True, "already_arrived": True, "input": deepcopy(existing),
                    "message": "迟到清洗输入已在领取后送达；刷新该条重检即可核对冲突"}

        if self.pending_late_input is not None and (
            entity_code == ENTITY_CODE
            or self.pending_late_input.get("entity_code") == entity_code
        ):
            late = self.pending_late_input
            self.pending_late_input = None
        else:
            late = self._build_late_input(entity_code)
        self.inputs.append(late)
        for item in store.rows("quality_recheck"):
            if item.get("entity_code") != entity_code:
                continue
            item["input_conflict"] = True
            item["conflict_message"] = (
                "输入凭据冲突：原报告使用 CRED-ORIG-X-0900（手机号、邮箱均空）；"
                "迟到输入 CRED-LATE-X-1030 已补齐手机号。刷新后可比较两份输入并选择重跑依据。"
            )
        return {"ok": True, "already_arrived": False, "input": deepcopy(late),
                "message": "新的清洗输入已迟到送达；请刷新重检视图以核对冲突和当前理由数"}

    def refresh_item(self, item_ref: Any, *, adopt: str = "latest") -> dict[str, Any]:
        item = self.find_item(item_ref)
        if item is None:
            return {"ok": False, "status_code": 404, "message": "重检清单不存在"}
        entity_code = _norm_id(item.get("entity_code") or item.get("实体编码"))
        if self.pending_late_input is not None:
            # 确定性演示/测试场景：第一次刷新时，领取后迟到的输入进入清单。
            self.arrive_late_input(entity_code or ENTITY_CODE)
        latest = self.latest_input(entity_code)
        original = self.find_input(item.get("effective_input_id")) or self.find_input("QIN-CUST-ORIG")
        if latest and latest.get("input_code") != (original or {}).get("input_code"):
            item["input_conflict"] = True
            item["conflict_message"] = (
                f"发现晚到输入 {latest['input_code']}（凭据 {latest.get('source_credential')}），"
                f"与原凭据 CRED-ORIG-X-0900 冲突；已保留原报告原因，可分别试算。"
            )
            if adopt in {"latest", "new", "late", "true"}:
                item["effective_input_id"] = latest["input_code"]
                item["adopted_input_id"] = latest["input_code"]
        else:
            item["input_conflict"] = False
        item["last_refreshed_at"] = now_iso()
        result = self.evaluate_item(item, item.get("effective_input_id"))
        item["current_reason_count"] = result["hit_count"]
        item["当前理由数"] = result["hit_count"]
        payload = self.serialize_item(item)
        if latest and original:
            payload["comparison"] = {
                "original_input": self._input_summary(original),
                "latest_input": self._input_summary(latest),
                "original_run": self.evaluate_item(item, original.get("input_code")),
                "latest_run": self.evaluate_item(item, latest.get("input_code")),
            }
        return {"ok": True, "message": "重检视图已按最新输入版本刷新", "item": payload}

    # ------------------------------------------------------------------
    # 规则重跑与服务端确认
    # ------------------------------------------------------------------
    def evaluate_item(self, item: dict[str, Any], input_ref: Any = None) -> dict[str, Any]:
        input_data = self.find_input(input_ref) if input_ref else None
        if input_data is None:
            input_data = self.find_input(item.get("effective_input_id"))
        if input_data is None:
            input_data = self.latest_input(_norm_id(item.get("entity_code") or item.get("实体编码")))
        reasons = self.reasons_for_item(item)
        record_id = _norm_id(item.get("record_id") or item.get("记录编号"))
        input_row: dict[str, Any] | None = None
        if input_data:
            input_row = next((deepcopy(row) for row in input_data.get("rows", [])
                              if _norm_id(row.get("record_id") or row.get("记录编号")) == record_id), None)

        checks: list[dict[str, Any]] = []
        for reason in reasons:
            field = reason.get("field") or reason.get("dimension")
            value = (input_row or {}).get(field, "") if input_row else ""
            passed = not _is_blank(value)
            checks.append({
                "rule_id": reason.get("rule_id"),
                "rule_code": reason.get("rule_code"),
                "rule_name": reason.get("rule_name"),
                "dimension": reason.get("dimension"),
                "field": field,
                "standard_code": reason.get("standard_code"),
                "rule_standard": reason.get("rule_standard"),
                "input_id": (input_data or {}).get("input_code"),
                "source_credential": (input_data or {}).get("source_credential"),
                "before_value": reason.get("actual_value", ""),
                "actual_value": value,
                "passed": passed,
                "hit": not passed,
                "result": "通过" if passed else "仍命中",
                "reason": "" if passed else f"按{reason.get('standard_code')}重跑，{field}仍为空",
            })
        hit_count = sum(1 for check in checks if check["hit"])
        total = len(checks)
        return {
            "ok": True,
            "input_id": (input_data or {}).get("input_code"),
            "input_code": (input_data or {}).get("input_code"),
            "input_label": (input_data or {}).get("label"),
            "source_credential": (input_data or {}).get("source_credential"),
            "input_row_found": input_row is not None,
            "input_row": input_row,
            "checks": checks,
            "check_total": total,
            "passed_count": total - hit_count,
            "hit_count": hit_count,
            "all_passed": hit_count == 0,
            "score": f"{((total - hit_count) / total * 100):.2f}%" if total else "100.00%",
            "ran_at": now_iso(),
        }

    def rerun_item(self, item_ref: Any, input_ref: Any = None) -> dict[str, Any]:
        """按指定实际输入试跑规则；只更新试算，不写最终报告轮次。"""
        item = self.find_item(item_ref)
        if item is None:
            return {"ok": False, "status_code": 404, "message": "重检清单不存在"}
        if input_ref:
            input_data = self.find_input(input_ref)
            if input_data is None:
                return {"ok": False, "message": "指定的检查输入版本不存在"}
            item["effective_input_id"] = input_data.get("input_code")
            item["adopted_input_id"] = input_data.get("input_code")
        result = self.evaluate_item(item, item.get("effective_input_id"))
        item["current_reason_count"] = result["hit_count"]
        item["当前理由数"] = result["hit_count"]
        item["trial_result"] = result
        return {"ok": True, "message": "规则已按所选实际输入试跑，尚未写入最终结果",
                "item": self.serialize_item(item), "result": result}

    def confirm_item(
        self,
        item_ref: Any,
        *,
        input_ref: Any = None,
        reviewer: str = "复查员",
        remark: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        item = self.find_item(item_ref)
        if item is None:
            return {"ok": False, "status_code": 404, "message": "重检清单不存在"}
        if item.get("status") == "已完成" and item.get("result_report_id") and not force:
            report = store.find("quality_result", int(item["result_report_id"]))
            return {"ok": True, "idempotent": True,
                    "message": "该条重检已经服务端确认，未重复写入报告轮次",
                    "item": self.serialize_item(item), "report": deepcopy(report)}

        entity_code = _norm_id(item.get("entity_code") or item.get("实体编码"))
        if input_ref:
            input_data = self.find_input(input_ref)
            if input_data is None:
                return {"ok": False, "message": "指定的检查输入版本不存在"}
        else:
            # 服务端确认时始终采用该实体最新的实际清洗输入；若要按原凭据复核，
            # 调用方必须显式传 original input id/code。
            input_data = self.latest_input(entity_code)
            if input_data is None:
                input_data = self.find_input(item.get("effective_input_id"))
        if input_data is None:
            return {"ok": False, "message": "找不到规则可重跑的实际清洗输入，不能用规则名称代替输入"}

        result = self.evaluate_item(item, input_data.get("input_code"))
        item["effective_input_id"] = input_data.get("input_code")
        item["adopted_input_id"] = input_data.get("input_code")
        item["rerun_result"] = result
        item["重跑结果"] = result
        item["current_reason_count"] = result["hit_count"]
        item["当前理由数"] = result["hit_count"]
        item["status"] = "已完成"
        item["pending"] = False
        item["abnormal"] = result["hit_count"] > 0
        item["confirmed_by"] = reviewer or "复查员"
        item["确认人"] = reviewer or "复查员"
        item["confirmed_at"] = now_iso()
        item["server_confirmed"] = True
        item["remark"] = remark
        item["复查意见"] = remark
        item["处置结论"] = ("复验通过：两项缺失均已补齐" if result["all_passed"]
                           else f"部分更正：通过 {result['passed_count']} 项，剩余 {result['hit_count']} 项命中，转入待处置")

        report = self._write_round_report(item, input_data, result)
        item["result_report_id"] = report["id"]
        item["本轮报告ID"] = report["id"]
        batch = self.batch_for_item(item)
        if batch:
            raw_batch = next((b for b in self.batches if b.get("batch_code") == batch.get("batch_code")), None)
            if raw_batch:
                self._recalc_batch(raw_batch)
        return {
            "ok": True,
            "message": "服务端已确认重检结果，并把本轮结果和采用的规则标准写回质量报告",
            "item": self.serialize_item(item),
            "report": report,
            "result": result,
        }

    def _write_round_report(
        self,
        item: dict[str, Any],
        input_data: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        root_id = item.get("root_report_id") or item.get("report_id")
        root = self.find_report(root_id) or {}
        rounds = [row for row in store.rows("quality_result") if row.get("root_report_id") == root_id]
        round_number = max((int(row.get("round_number", 1) or 1) for row in rounds), default=1) + 1
        round_code = f"R{round_number}"
        report_id = max((int(row.get("id", 0) or 0) for row in store.rows("quality_result")), default=ORIG_REPORT_ID) + 1
        standards = list(dict.fromkeys(check.get("rule_standard", "") for check in result["checks"]))
        dimensions = "、".join(check.get("dimension", "") for check in result["checks"])
        correction = (
            f"采用输入 {input_data.get('input_code')}（凭据 {input_data.get('source_credential')}）；"
            f"检查依据：{'；'.join(filter(None, standards))}。"
            f"规则重跑 {result['check_total']} 项，通过 {result['passed_count']} 项，"
            f"剩余命中 {result['hit_count']} 项，得分 {result['score']}。"
        )
        report = {
            "id": report_id,
            "status": "已生成",
            "pending": False,
            "abnormal": result["hit_count"] > 0,
            "报告批次": f"{root.get('报告批次', item.get('原报告批次'))}-{round_code}",
            "report_code": f"{root.get('报告批次', item.get('原报告批次'))}-{round_code}",
            "实体编码": item.get("实体编码"),
            "entity_code": item.get("entity_code"),
            "实体名称": item.get("实体名称"),
            "检查总数": str(result["check_total"]),
            "命中数": str(result["hit_count"]),
            "受影响记录数": "1",
            "评分结果": result["score"],
            "报告轮次": round_code,
            "round": round_code,
            "round_number": round_number,
            "root_report_id": root_id,
            "parent_report_id": root_id,
            "recheck_id": item.get("id"),
            "recheck_code": item.get("recheck_code"),
            "重检批次": item.get("重检批次"),
            "检查维度": dimensions,
            "使用规则标准": "；".join(filter(None, standards)),
            "used_standards": standards,
            "采用输入ID": input_data.get("input_code"),
            "adopted_input_id": input_data.get("input_code"),
            "实际使用输入": deepcopy(input_data),
            "更正说明": correction,
            "correction_note": correction,
            "本轮检查结果": deepcopy(result),
            "original_hits_preserved": True,
            "generated_at": now_iso(),
        }
        # 保留原报告在列表前部；新一轮结果按生成顺序追加，避免覆盖原报告身份。
        store.rows("quality_result").append(report)
        return deepcopy(report)

    # ------------------------------------------------------------------
    # 质量规则库关联
    # ------------------------------------------------------------------
    def rule_context(self, rule_ref: Any) -> dict[str, Any] | None:
        rule = self.find_rule(rule_ref)
        if rule is None:
            return None
        rule_id = rule.get("id")
        hits = [deepcopy(hit) for hit in self.hits
                if hit.get("rule_id") == rule_id or hit.get("rule_code") == rule.get("rule_code")]
        hit_ids = {hit["id"] for hit in hits}
        items = []
        for item in store.rows("quality_recheck"):
            if hit_ids & set(item.get("reason_ids", [])):
                items.append(self.serialize_item(item))
        input_codes = {hit.get("input_id") for hit in hits}
        for item in items:
            input_codes.add(item.get("adopted_input_id"))
            if item.get("rerun_result"):
                input_codes.add(item["rerun_result"].get("input_id"))
        inputs = [self.find_input(code) for code in input_codes]
        inputs = [data for data in inputs if data]
        report_ids = {hit.get("report_id") for hit in hits}
        reports = [deepcopy(report) for report in store.rows("quality_result") if report.get("id") in report_ids]
        links = []
        for item in items:
            links.append({
                "recheck_item_id": item.get("id"),
                "recheck_code": item.get("recheck_code"),
                "batch_code": item.get("batch_code"),
                "record_id": item.get("record_id"),
                "report_id": item.get("report_id"),
                "report_batch": item.get("report_batch"),
                "checklist": item.get("reasons"),
                "original_input": next((data for data in inputs
                                        if data.get("input_code") == "QIN-CUST-ORIG"), None),
                "used_input": item.get("effective_input"),
            })
        return {
            "ok": True,
            "rule": deepcopy(rule),
            "linked_hits": hits,
            "recheck_items": items,
            "recheck_requests": links,
            "recheck_lists": links,
            "reports": reports,
            "inputs": inputs,
            "actual_inputs": inputs,
            "actual_input": inputs[-1] if inputs else None,
        }

    def all_rule_links(self) -> dict[str, Any]:
        canonical = [PHONE_RULE_ID, EMAIL_RULE_ID]
        contexts = [self.rule_context(rule_id) for rule_id in canonical]
        contexts = [context for context in contexts if context]
        return {"ok": True, "items": contexts, "total": len(contexts)}

    def input_rows_for_rule(
        self,
        rule: dict[str, Any],
        *,
        recheck_id: Any = None,
        report_id: Any = None,
    ) -> list[dict[str, Any]]:
        """替代旧实现错误返回的“规则名称列表”，返回规则可重跑的实际输入行。"""
        entity_code = _norm_id(rule.get("实体编码") or rule.get("entity_code"))
        item = self.find_item(recheck_id) if recheck_id is not None else None
        if item is not None:
            input_data = self.find_input(item.get("effective_input_id")) or self.latest_input(entity_code)
        elif report_id is not None:
            report = self.find_report(report_id)
            input_data = self.find_input((report or {}).get("实际输入ID")) or self.latest_input(entity_code)
        else:
            input_data = self.latest_input(entity_code)
            if input_data is None and entity_code == ENTITY_CODE:
                input_data = self.find_input("QIN-CUST-ORIG")
        return deepcopy((input_data or {}).get("rows", []))


workflow = QualityWorkflow()


def ensure_quality_workflow() -> QualityWorkflow:
    workflow.ensure()
    return workflow
