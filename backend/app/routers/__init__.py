"""业务路由汇总：质量钻取专用路由先注册，其后是所有模块共用的资源路由。"""
from __future__ import annotations

from app.routers import quality, resource

ROUTERS = [quality, resource]
