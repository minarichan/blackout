from fastapi import APIRouter, Request

from app.api.portfolio import _client_key, _service

router = APIRouter()


@router.get("/portfolio/{address}/risk")
async def risk(address: str, request: Request, refresh: bool = False) -> dict:
    book = await _service(request).get_portfolio(address, refresh=refresh, client_key=_client_key(request))
    return {
        "address": book.address,
        "summary": book.summary,
        "accounts": book.accounts,
        "concentration": book.concentration,
        "stress": book.stress,
        "methodology": book.methodology,
    }


@router.get("/portfolio/{address}/alerts")
async def alerts(address: str, request: Request, refresh: bool = False) -> dict:
    book = await _service(request).get_portfolio(address, refresh=refresh, client_key=_client_key(request))
    return {"address": book.address, "alerts": book.alerts, "data_quality": book.data_quality}
