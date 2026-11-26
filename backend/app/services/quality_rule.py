"""质量规则库领域服务：管理主数据质量检查规则、阈值口径、严重级别与命中统计。

数据链路位置：质量治理层规则端，负责消费清洗产物执行检查，
把命中结果派发给质量报告模块。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class QualityRuleService(BaseModuleService):
    MODULE = "quality_rule"
    ENTITY = "质量规则"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["规则名称", "实体编码", "检查维度", "阈值口径", "严重级别"]
    REQUIRED_FIELDS = ["规则名称", "实体编码", "检查维度"]
    STATUS_ORDER = ["草稿", "已启用", "已停用"]
    ACTION_RULES = {"启用规则": "已启用", "停用规则": "已停用"}
    NEGATIVE_ACTIONS = ["停用规则"]

    # ---- 业务扩展：质量规则命中与报告派发 ----

    def check_threshold(self, entry_id: int, value: float) -> dict[str, Any]:
        """按阈值口径判定命中，严重级别决定处置。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return {"ok": False, "message": "质量规则不存在"}
        raw = str(entry.get("阈值口径", "0.9")).rstrip("%")
        try:
            threshold = float(raw)
        except ValueError:
            threshold = 0.9
        hit = value < threshold
        if hit:
            entry["今日命中"] = str(int(entry.get("今日命中", "0") or 0) + 1)
        return {"ok": True, "hit": hit, "threshold": threshold,
                "severity": entry.get("严重级别", "中"), "value": value}

    def run_rule_batch(self, entry_id: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """批量执行质量规则，输出命中的记录集合。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None or entry.get("status") != "已启用":
            return {"ok": False, "message": "规则未启用", "hits": []}
        dimension = str(entry.get("检查维度", ""))
        hits = [r for r in rows if not str(r.get(dimension, "")).strip()]
        entry["今日命中"] = str(int(entry.get("今日命中", "0") or 0) + len(hits))
        return {"ok": True, "hits": hits, "checked": len(rows), "dimension": dimension}

    def dispatch_result_report(self, entry_id: int, hit_count: int, total: int) -> int:
        """派发质量报告生成任务到 quality_result 模块。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return 0
        results = store.rows("quality_result")
        report_id = max((int(r.get("id", 0)) for r in results), default=0) + 1
        score = f"{(1 - hit_count / total):.2f}" if total else "1.00"
        results.append({
            "id": report_id,
            "报告批次": f"qr-{entry.get('规则名称')}-{report_id}",
            "实体编码": entry.get("实体编码", ""),
            "检查总数": str(total),
            "命中数": str(hit_count),
            "评分结果": score,
            "status": "已生成",
            "pending": False,
            "abnormal": hit_count > 0,
        })
        return report_id

    def consume_cleanse_output(
        self,
        entry_id: int,
        recheck_id: int | str | None = None,
        report_id: int | str | None = None,
    ) -> list[dict[str, Any]]:
        """读取规则实际检查的清洗输出行。

        旧实现返回同实体下清洗规则的“规则名称”，会把规则名误当成整份输入；
        质量复查必须返回可打开、可重跑的真实数据行。优先读取质量工作流保存的
        输入快照，也兼容清洗模块行内登记的 ``rows`` / ``输出数据``。
        """
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return []
        from app.quality_workflow import workflow

        rows = workflow.input_rows_for_rule(
            entry, recheck_id=recheck_id, report_id=report_id)
        if rows:
            return rows

        entity_code = str(entry.get("实体编码") or entry.get("entity_code") or "")
        for cleanse in store.rows("std_cleanse"):
            if entity_code and cleanse.get("实体编码") != entity_code:
                continue
            for key in ("input_rows", "rows", "actual_input", "实际输入", "输出数据", "清洗输出"):
                value = cleanse.get(key)
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return value
        return []

    def quality_context(self, entry_id: int) -> dict[str, Any] | None:
        """规则库查看关联重检清单、原报告输入和本次实际采用输入。"""
        from app.quality_workflow import workflow

        return workflow.rule_context(entry_id)

    def disable_with_reason(self, entry_id: int, reason: str) -> str:
        """停用规则并登记停用原因，防止误启用。"""
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return "质量规则不存在"
        entry["status"] = "已停用"
        entry["abnormal"] = True
        entry["停用原因"] = reason
        return f"规则 {entry.get('规则名称')} 已停用: {reason}"

    def align_severity_order(self, entry_id: int, min_severity: str) -> bool:
        """校准严重级别顺序，确保告警口径统一。"""
        order = {"低": 0, "中": 1, "高": 2}
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return False
        current = str(entry.get("严重级别", "中"))
        if order.get(current, 1) < order.get(min_severity, 1):
            entry["严重级别"] = min_severity
            return True
        return False
