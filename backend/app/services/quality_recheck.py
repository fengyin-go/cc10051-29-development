"""质量复查（重检清单）通用资源服务。

完整钻取、输入版本和重跑逻辑在 ``app.quality_workflow``；本类只把通用
``/api/quality_recheck`` 列表和动作入口接到同一工作流，避免出现两套状态。
"""
from __future__ import annotations

from typing import Any

from app.quality_workflow import workflow
from app.services.base import BaseModuleService
from app.store import store


class QualityRecheckService(BaseModuleService):
    MODULE = "quality_recheck"
    ENTITY = "质量复查"
    OPERATION_TERM = "重检"
    LIST_FIELDS = [
        "重检批次",
        "原报告批次",
        "报告轮次",
        "实体编码",
        "记录编号",
        "记录名称",
        "命中维度",
        "当前理由数",
        "状态",
        "复查员",
    ]
    REQUIRED_FIELDS = ["重检批次", "原报告批次", "实体编码", "记录编号"]
    STATUS_ORDER = ["待领取", "处理中", "已完成"]
    ACTION_RULES = {
        "领取": "处理中",
        "领取重检": "处理中",
        "继续领取": "处理中",
        "刷新重检": "处理中",
        "确认重检结果": "已完成",
        "完成重检": "已完成",
    }
    NEGATIVE_ACTIONS = []

    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """通用列表也返回带理由、输入和试算结果的完整复查视图。"""
        conditions = filters or {}
        result = workflow.list_rechecks(
            entity_code=conditions.get("实体编码", ""),
            report_round=conditions.get("报告轮次", ""),
            status=status or "",
            batch_code=conditions.get("重检批次", ""),
            keyword=keyword or "",
        )
        rows = result["items"]
        total = len(rows)
        start = (page - 1) * size
        return rows[start:start + size], total

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        text = action.strip()
        if "领取" in text:
            result = workflow.claim(entry_id)
        elif "刷新" in text:
            result = workflow.refresh_item(entry_id)
        elif any(word in text for word in ("确认", "完成", "办结", "重跑")):
            result = workflow.confirm_item(entry_id)
        else:
            return super().run_action(entry_id, text)

        if not result.get("ok"):
            return None, str(result.get("message", "质量复查操作失败"))
        item = result.get("item") or store.find(self.MODULE, entry_id)
        return item, str(result.get("message", "操作完成"))
