"""Version info endpoint."""

from __future__ import annotations

import sys

from fastapi import APIRouter, Depends

from backend.schemas.version import VersionResponse
from core.config import AppConfig

from backend.api.deps import get_app_config

router = APIRouter()


@router.get("/version", response_model=VersionResponse)
def version_info(cfg: AppConfig = Depends(get_app_config)) -> VersionResponse:
    return VersionResponse(
        name=cfg.app_name,
        version=cfg.version,
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
