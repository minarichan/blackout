from fastapi import APIRouter, Request

from app.api.portfolio import _client_key, _service
from app.models.schemas import IngestionOut, PositionOut

router = APIRouter()


@router.get("/portfolio/{address}/positions")
async def positions(address: str, request: Request, refresh: bool = False) -> dict:
    book = await _service(request).get_portfolio(address, refresh=refresh, client_key=_client_key(request))
    payload: dict[str, list[PositionOut] | list[IngestionOut] | str] = {
        "address": book.address,
        "positions": book.positions,
        "ingestion": book.ingestion,
    }
    return payload
