"""质量报告钻取、质量复查和规则输入关联的专用 HTTP 接口。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.quality_workflow import workflow

router = APIRouter(prefix="/api", tags=["质量钻取与复查"])


async def payload_dict(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001 - 空请求体按默认参数处理
        return {}
    return data if isinstance(data, dict) else {}


def ok_or_raise(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("ok"):
        raise HTTPException(
            status_code=int(result.get("status_code") or 400),
            detail=str(result.get("message") or "质量复查操作失败"),
        )
    return result


# ----------------------------------------------------------------------
# 报告钻取与发起重检
# ----------------------------------------------------------------------
for path in (
    "/quality_result/{report_ref}/drilldown",
    "/quality_result/{report_ref}/hit-sources",
    "/quality-reports/{report_ref}/drilldown",
    "/quality/reports/{report_ref}/drilldown",
):
    @router.get(path)
    def report_drilldown(report_ref: str) -> dict[str, Any]:
        result = workflow.report_drilldown(report_ref)
        if result is None:
            raise HTTPException(status_code=404, detail="原质量报告不存在")
        return result


for path in (
    "/quality_result/{report_ref}/detail",
    "/quality_result/{report_ref}/rounds",
    "/quality-reports/{report_ref}/detail",
):
    @router.get(path)
    def report_detail(report_ref: str) -> dict[str, Any]:
        result = workflow.report_detail(report_ref)
        if result is None:
            raise HTTPException(status_code=404, detail="原质量报告不存在")
        return result


for path in (
    "/quality_result/{report_ref}/rechecks",
    "/quality_result/{report_ref}/recheck",
    "/quality_result/{report_ref}/recheck-list",
    "/quality_result/{report_ref}/recheck_list",
    "/quality-reports/{report_ref}/rechecks",
    "/quality/reports/{report_ref}/rechecks",
):
    @router.post(path)
    async def create_rechecks(report_ref: str, request: Request) -> dict[str, Any]:
        data = await payload_dict(request)
        return ok_or_raise(workflow.create_rechecks(
            report_ref,
            hit_ids=_extract_hit_ids(data),
            record_ids=data.get("record_ids") or data.get("row_ids"),
            reviewer=str(data.get("reviewer") or data.get("复查员") or ""),
        ))


@router.get("/quality_result/{report_ref}/rechecks")
@router.get("/quality_result/{report_ref}/recheck-list")
def get_report_rechecks(report_ref: str) -> dict[str, Any]:
    report = workflow.find_report(report_ref)
    if report is None:
        raise HTTPException(status_code=404, detail="原质量报告不存在")
    rid = report.get("id")
    items = [
        workflow.serialize_item(item)
        for item in store_rows_quality_recheck()
        if item.get("report_id") == rid
    ]
    return {"ok": True, "report": report, "items": items, "total": len(items)}


def store_rows_quality_recheck() -> list[dict[str, Any]]:
    from app.store import store

    return store.rows("quality_recheck")


def _extract_hit_ids(data: dict[str, Any]) -> list[Any] | None:
    hit_ids = (
        data.get("hit_ids")
        or data.get("selected_hit_ids")
        or data.get("selected")
        or data.get("ids")
    )
    if hit_ids:
        return hit_ids if isinstance(hit_ids, list) else [hit_ids]
    items = data.get("items") or data.get("recheck_items") or data.get("hits")
    if isinstance(items, list):
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(item.get("hit_id") or item.get("id") or item.get("reason_id"))
            else:
                result.append(item)
        return [value for value in result if value is not None]
    return None


for path in (
    "/rechecks",
    "/quality_recheck",
    "/quality_rechecks",
    "/quality_review",
    "/quality_reviews",
):
    @router.post(path)
    async def create_recheck_collection(request: Request) -> dict[str, Any]:
        data = await payload_dict(request)
        report_ref = (
            data.get("report_id")
            or data.get("report_ref")
            or data.get("root_report_id")
            or data.get("原报告ID")
            or data.get("原报告批次")
            or data.get("report_batch")
        )
        if isinstance(data.get("report"), dict):
            report_ref = report_ref or data["report"].get("id") or data["report"].get("报告批次")
        if report_ref:
            return ok_or_raise(workflow.create_rechecks(
                report_ref,
                hit_ids=_extract_hit_ids(data),
                record_ids=data.get("record_ids") or data.get("row_ids"),
                reviewer=str(data.get("reviewer") or data.get("复查员") or ""),
            ))

        # 没有报告身份时，保持通用资源登记契约。
        from app.services.quality_recheck import QualityRecheckService

        values = data.get("values") if isinstance(data.get("values"), dict) else data
        entry, missing = QualityRecheckService().create_entry(values)
        if missing:
            return {"ok": False, "message": f"缺少必填字段：{'、'.join(missing)}", "entry": None}
        return {"ok": True, "message": "质量复查记录已登记", "entry": entry}


# ----------------------------------------------------------------------
# 质量复查清单、领取、刷新、迟到输入、确认重跑
# ----------------------------------------------------------------------
@router.get("/rechecks")
@router.get("/quality-workflow/rechecks")
@router.get("/quality/rechecks")
@router.get("/quality-rechecks")
@router.get("/quality_rechecks")
@router.get("/quality_recheck/list")
@router.get("/quality_recheck/affected")
@router.get("/quality_review/list")
@router.get("/quality_review/affected")
def list_rechecks(
    entity_code: str = Query(default=""),
    entity: str = Query(default=""),
    report_round: str = Query(default=""),
    round: str = Query(default=""),
    status: str = Query(default=""),
    batch: str = Query(default=""),
    batch_code: str = Query(default=""),
    keyword: str = Query(default=""),
) -> dict[str, Any]:
    return workflow.list_rechecks(
        entity_code=entity_code or entity,
        report_round=report_round or round,
        status=status,
        batch_code=batch_code or batch,
        keyword=keyword,
    )


@router.get("/rechecks/{item_ref}")
@router.get("/quality-workflow/rechecks/{item_ref}")
@router.get("/quality/rechecks/{item_ref}")
@router.get("/quality-review/{item_ref}")
def get_recheck(item_ref: str) -> dict[str, Any]:
    item = workflow.find_item(item_ref)
    if item is None:
        raise HTTPException(status_code=404, detail="重检清单不存在")
    return {"ok": True, "item": workflow.serialize_item(item)}


@router.get("/quality_recheck/{item_ref}/detail")
def get_named_recheck_detail(item_ref: str) -> dict[str, Any]:
    return get_recheck(item_ref)


@router.get("/quality_recheck/{item_ref}")
@router.get("/quality_review/{item_ref}")
def get_recheck_resource(item_ref: str) -> dict[str, Any]:
    item = workflow.find_item(item_ref)
    if item is None:
        raise HTTPException(status_code=404, detail="重检清单不存在")
    # 与通用 /api/{module}/{id} 契约保持一致：直接返回条目，不套 {item}。
    return workflow.serialize_item(item)


for action in ("claim", "refresh", "rerun", "confirm", "complete"):
    for prefix in (
        "/rechecks/{item_ref}",
        "/quality-workflow/rechecks/{item_ref}",
        "/quality_recheck/{item_ref}",
        "/quality_review/{item_ref}",
        "/quality-review/{item_ref}",
    ):
        path = f"{prefix}/{action}"

        def make_endpoint(act: str = action):
            async def endpoint(item_ref: str, request: Request) -> dict[str, Any]:
                data = await payload_dict(request)
                reviewer = str(data.get("reviewer") or data.get("复查员") or "复查员")
                if act == "claim":
                    return ok_or_raise(workflow.claim(item_ref, reviewer))
                if act == "refresh":
                    return ok_or_raise(workflow.refresh_item(
                        item_ref, adopt=str(data.get("adopt") or "latest")))
                if act == "rerun":
                    return ok_or_raise(workflow.rerun_item(
                        item_ref,
                        input_ref=data.get("input_id") or data.get("input_ref"),
                    ))
                # confirm/complete 由服务端按规则标准实际重跑并写回新一轮结果。
                result = workflow.confirm_item(
                    item_ref,
                    input_ref=data.get("input_id") or data.get("input_ref"),
                    reviewer=reviewer,
                    remark=str(data.get("remark") or data.get("复查意见") or ""),
                    force=bool(data.get("force", False)),
                )
                return ok_or_raise(result)
            return endpoint

        router.add_api_route(path, make_endpoint(), methods=["POST"])


for path in (
    "/quality-workflow/late-inputs",
    "/quality-workflow/scenarios/late-cleanse-input",
    "/quality_recheck/late-input",
    "/quality-inputs/late",
):
    @router.post(path)
    async def arrive_late_input(request: Request) -> dict[str, Any]:
        data = await payload_dict(request)
        entity_code = str(data.get("entity_code") or data.get("实体编码") or "CUSTOMER")
        return workflow.arrive_late_input(entity_code)


@router.post("/quality_recheck/{item_ref}/simulate-late-input")
async def simulate_late_for_item(item_ref: str) -> dict[str, Any]:
    item = workflow.find_item(item_ref)
    if item is None:
        raise HTTPException(status_code=404, detail="重检清单不存在")
    entity_code = str(item.get("entity_code") or item.get("实体编码") or "CUSTOMER")
    return workflow.arrive_late_input(entity_code)


# ----------------------------------------------------------------------
# 质量规则库：关联重检清单、原报告输入和实际采用输入
# ----------------------------------------------------------------------
@router.get("/quality-workflow/rule-links")
def all_rule_links() -> dict[str, Any]:
    return workflow.all_rule_links()


for path in (
    "/quality_rule/{rule_ref}/quality-context",
    "/quality_rule/{rule_ref}/recheck-relations",
    "/quality_rule/{rule_ref}/recheck-context",
    "/quality-workflow/rules/{rule_ref}/context",
):
    @router.get(path)
    def rule_context(rule_ref: str) -> dict[str, Any]:
        result = workflow.rule_context(rule_ref)
        if result is None:
            raise HTTPException(status_code=404, detail="质量规则不存在")
        return result


for path in (
    "/quality_rule/{rule_ref}/actual-input",
    "/quality-workflow/rules/{rule_ref}/actual-input",
):
    @router.get(path)
    def rule_actual_input(rule_ref: str, recheck_id: str | None = None,
                          report_id: str | None = None) -> dict[str, Any]:
        context = workflow.rule_context(rule_ref)
        if context is None:
            raise HTTPException(status_code=404, detail="质量规则不存在")
        rows = workflow.input_rows_for_rule(
            context["rule"], recheck_id=recheck_id, report_id=report_id)
        return {"ok": True, "rule": context["rule"], "rows": rows,
                "actual_inputs": context["actual_inputs"]}
