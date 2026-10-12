from fastapi import APIRouter

from app.config import get_settings
from app.registry import protocols_payload

router = APIRouter()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "chains": settings.enabled_chain_list,
        "protocols": ["aave-v3", "compound-v3"],
    }


@router.get("/protocols")
def protocols() -> dict:
    return protocols_payload(get_settings().enabled_chain_list)
