"""领域服务注册表：通用资源路由按模块 key 分派到独立业务服务。"""
from __future__ import annotations

from app.services.base import BaseModuleService
from app.services.source_system import SourceSystemService
from app.services.entity_model import EntityModelService
from app.services.record_extract import RecordExtractService
from app.services.std_cleanse import StdCleanseService
from app.services.dup_detect import DupDetectService
from app.services.golden_merge import GoldenMergeService
from app.services.golden_publish import GoldenPublishService
from app.services.subscriber_mgr import SubscriberMgrService
from app.services.dist_task import DistTaskService
from app.services.lineage_graph import LineageGraphService
from app.services.quality_rule import QualityRuleService
from app.services.quality_result import QualityResultService
from app.services.quality_recheck import QualityRecheckService
from app.services.merge_review import MergeReviewService
from app.services.version_rollback import VersionRollbackService
from app.services.sync_cursor import SyncCursorService
from app.services.id_cross_map import IdCrossMapService
from app.services.dist_receipt import DistReceiptService
from app.services.model_change import ModelChangeService
from app.services.stats_overview import StatsOverviewService
from app.services.ref_data_mgr import RefDataMgrService

SERVICES: dict[str, BaseModuleService] = {
    "source_system": SourceSystemService(),
    "entity_model": EntityModelService(),
    "record_extract": RecordExtractService(),
    "std_cleanse": StdCleanseService(),
    "dup_detect": DupDetectService(),
    "golden_merge": GoldenMergeService(),
    "golden_publish": GoldenPublishService(),
    "subscriber_mgr": SubscriberMgrService(),
    "dist_task": DistTaskService(),
    "lineage_graph": LineageGraphService(),
    "quality_rule": QualityRuleService(),
    "quality_result": QualityResultService(),
    "quality_recheck": QualityRecheckService(),
    "quality_review": QualityRecheckService(),
    "merge_review": MergeReviewService(),
    "version_rollback": VersionRollbackService(),
    "sync_cursor": SyncCursorService(),
    "id_cross_map": IdCrossMapService(),
    "dist_receipt": DistReceiptService(),
    "model_change": ModelChangeService(),
    "stats_overview": StatsOverviewService(),
    "ref_data_mgr": RefDataMgrService(),
}


def service_for(module: str) -> BaseModuleService | None:
    return SERVICES.get(module)


# 导入服务时即装载质量钻取/重检示例场景，保证通用资源与自定义接口状态一致。
from app.quality_workflow import ensure_quality_workflow  # noqa: E402

ensure_quality_workflow()
