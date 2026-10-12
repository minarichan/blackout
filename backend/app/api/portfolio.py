from fastapi import APIRouter, Request

from app.models.schemas import PortfolioOut, SnapshotOut, WatchIn, WatchOut
from app.services.portfolio_service import PortfolioService

router = APIRouter()


def _service(request: Request) -> PortfolioService:
    return request.app.state.service


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "local"


@router.get("/portfolio/{address}", response_model=PortfolioOut)
async def portfolio(address: str, request: Request, refresh: bool = False) -> PortfolioOut:
    return await _service(request).get_portfolio(address, refresh=refresh, client_key=_client_key(request))


@router.get("/portfolio/{address}/history", response_model=list[SnapshotOut])
def history(address: str, request: Request) -> list[SnapshotOut]:
    return _service(request).history(address)


@router.get("/watchlist", response_model=list[WatchOut])
def list_watchlist(request: Request) -> list[WatchOut]:
    return _service(request).list_watchlist()


@router.post("/watchlist", response_model=WatchOut)
def save_watch(body: WatchIn, request: Request) -> WatchOut:
    return _service(request).save_watch(body.address, body.label)


@router.delete("/watchlist/{address}", status_code=204)
def delete_watch(address: str, request: Request) -> None:
    from fastapi import HTTPException

    if not _service(request).delete_watch(address):
        raise HTTPException(status_code=404, detail="Address is not on the watchlist.")
