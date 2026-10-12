from __future__ import annotations

from decimal import Decimal

from app.core.assets import factor_bucket
from app.models.risk import Alert, Analysis
from app.registry import CHAINS

ZERO = Decimal("0")
HF_CRITICAL = Decimal("1.05")
HF_HIGH = Decimal("1.20")
HF_ELEVATED = Decimal("1.50")
DIST_CRITICAL = Decimal("0.05")
DIST_HIGH = Decimal("0.10")
DIST_ELEVATED = Decimal("0.20")
FACTOR_HIGH = Decimal("0.80")
FACTOR_ELEVATED = Decimal("0.60")
CHAIN_HIGH = Decimal("0.80")
CHAIN_ELEVATED = Decimal("0.65")
ASSET_HIGH = Decimal("0.75")
ASSET_ELEVATED = Decimal("0.55")
MODEL_GAP = Decimal("0.03")

SEVERITY_RANK = {"critical": 0, "high": 1, "elevated": 2, "info": 3}

PRIMARY_LABEL = {
    "collateral_drawdown": "collateral can fall",
    "debt_expansion": "debt can rise",
    "mixed": "mixed price move",
    "none": "no debt",
}


def _pct(value: Decimal) -> str:
    return f"{(value * Decimal('100')):.1f}%"


def _hf(value: Decimal) -> str:
    return f"{value:.2f}"


def _alert(**kwargs: object) -> Alert:
    return Alert(**kwargs)  # type: ignore[arg-type]


def _health_alerts(analysis: Analysis) -> list[Alert]:
    alerts: list[Alert] = []
    for account in analysis.accounts:
        health = account.health_factor
        if health is None:
            continue
        scope = f"{account.market_name} on {account.chain}"
        if health < Decimal("1"):
            alerts.append(
                _alert(
                    id=f"liquidatable:{account.account_key}",
                    severity="critical",
                    code="liquidatable",
                    title=f"Liquidatable · {scope}",
                    detail=f"Health factor is {_hf(health)}. This account is already through the liquidation boundary.",
                    chain=account.chain,
                    protocol=account.protocol,
                    account_key=account.account_key,
                )
            )
        elif health < HF_CRITICAL:
            alerts.append(
                _alert(
                    id=f"health:{account.account_key}",
                    severity="critical",
                    code="health_critical",
                    title=f"Health {_hf(health)} · {scope}",
                    detail="Health is inside 1.05. A small oracle or price move can liquidate this account.",
                    chain=account.chain,
                    protocol=account.protocol,
                    account_key=account.account_key,
                )
            )
        elif health < HF_HIGH:
            alerts.append(
                _alert(
                    id=f"health:{account.account_key}",
                    severity="high",
                    code="health_high",
                    title=f"Health {_hf(health)} · {scope}",
                    detail="Health is under 1.20. This is the account that needs attention first.",
                    chain=account.chain,
                    protocol=account.protocol,
                    account_key=account.account_key,
                )
            )
        elif health < HF_ELEVATED:
            alerts.append(
                _alert(
                    id=f"health:{account.account_key}",
                    severity="elevated",
                    code="health_elevated",
                    title=f"Health {_hf(health)} · {scope}",
                    detail="Health is under 1.50. Usable, but not a comfortable buffer.",
                    chain=account.chain,
                    protocol=account.protocol,
                    account_key=account.account_key,
                )
            )

        distance = account.primary_distance_pct
        if distance is None or health < Decimal("1"):
            continue
        kind = PRIMARY_LABEL.get(account.primary_risk, "price move")
        if distance < DIST_CRITICAL:
            severity, code = "critical", "distance_critical"
        elif distance < DIST_HIGH:
            severity, code = "high", "distance_high"
        elif distance < DIST_ELEVATED:
            severity, code = "elevated", "distance_elevated"
        else:
            continue
        alerts.append(
            _alert(
                id=f"distance:{account.account_key}",
                severity=severity,
                code=code,
                title=f"{_pct(distance)} room · {scope}",
                detail=f"Primary path is {kind}. Isolated from other accounts.",
                chain=account.chain,
                protocol=account.protocol,
                account_key=account.account_key,
            )
        )

        computed = account.computed_health_factor
        protocol = account.protocol_health_factor
        if computed is not None and protocol is not None and protocol > ZERO:
            gap = abs(protocol - computed) / protocol
            if gap > MODEL_GAP:
                alerts.append(
                    _alert(
                        id=f"model-gap:{account.account_key}",
                        severity="info",
                        code="health_model_gap",
                        title=f"Protocol health differs · {scope}",
                        detail=(
                            f"The protocol reports {_hf(protocol)} and the recomputed health is {_hf(computed)}. "
                            "The headline uses the protocol figure, which is what liquidations use."
                        ),
                        chain=account.chain,
                        protocol=account.protocol,
                        account_key=account.account_key,
                    )
                )
    return alerts


def _share_alerts(analysis: Analysis) -> list[Alert]:
    alerts: list[Alert] = []
    concentration = analysis.concentration

    def emit_top(
        rows: list,
        *,
        code: str,
        elevated: Decimal,
        high: Decimal,
        noun: str,
        book: str,
    ) -> None:
        if not rows:
            return
        top = rows[0]
        if top.share < elevated:
            return
        severity = "high" if top.share >= high else "elevated"
        label = _slice_label(code, top.key)
        alerts.append(
            _alert(
                id=f"{code}:{book}:{top.key}",
                severity=severity,
                code=code,
                title=f"{label} is {_pct(top.share)} of {book}",
                detail=f"{noun} A single-name or single-venue move dominates this book.",
                asset=top.key if "asset" in code or code.startswith("factor") else None,
            )
        )

    emit_top(
        concentration.collateral_by_asset,
        code="collateral_concentration",
        elevated=ASSET_ELEVATED,
        high=ASSET_HIGH,
        noun="Collateral is concentrated in one asset.",
        book="collateral",
    )
    emit_top(
        concentration.debt_by_asset,
        code="debt_concentration",
        elevated=ASSET_ELEVATED,
        high=ASSET_HIGH,
        noun="Debt is concentrated in one asset.",
        book="debt",
    )
    emit_top(
        concentration.collateral_by_chain,
        code="chain_concentration",
        elevated=CHAIN_ELEVATED,
        high=CHAIN_HIGH,
        noun="Collateral sits mostly on one chain.",
        book="collateral",
    )
    emit_top(
        concentration.collateral_by_factor,
        code="factor_concentration",
        elevated=FACTOR_ELEVATED,
        high=FACTOR_HIGH,
        noun="Collateral shares one market factor.",
        book="collateral",
    )
    return alerts


def _slice_label(code: str, key: str) -> str:
    if code == "chain_concentration":
        chain = CHAINS.get(key)
        return chain.name if chain else key
    if code == "factor_concentration":
        return {
            "eth": "ETH",
            "btc": "BTC",
            "usdc": "USDC",
            "stable": "Stables",
            "soft_stable": "Soft stables",
            "alt": "Alts",
        }.get(key, key)
    return key


def _correlation_alerts(analysis: Analysis) -> list[Alert]:
    alerts: list[Alert] = []
    collateral_factors = {row.key: row.share for row in analysis.concentration.collateral_by_factor}
    debt_factors = {row.key: row.share for row in analysis.concentration.debt_by_factor}
    eth_collateral = collateral_factors.get("eth", ZERO)
    stable_debt = debt_factors.get("usdc", ZERO) + debt_factors.get("stable", ZERO)
    eth_debt = debt_factors.get("eth", ZERO)
    stable_collateral = collateral_factors.get("usdc", ZERO) + collateral_factors.get("stable", ZERO)

    if eth_collateral >= Decimal("0.5") and stable_debt >= Decimal("0.5"):
        alerts.append(
            _alert(
                id="correlation:long-eth",
                severity="elevated",
                code="correlation_directional_long",
                title="Directional long ETH against stables",
                detail=(
                    f"ETH-family collateral is {_pct(eth_collateral)} and stable debt is {_pct(stable_debt)}. "
                    "An ETH drawdown tightens health. An ETH rally does not."
                ),
                asset="ETH",
            )
        )
    if eth_debt >= Decimal("0.35") and stable_collateral >= Decimal("0.25"):
        alerts.append(
            _alert(
                id="correlation:short-eth",
                severity="elevated",
                code="correlation_directional_short",
                title="ETH debt against stable collateral",
                detail=(
                    f"ETH-family debt is {_pct(eth_debt)} of debt and stable collateral is {_pct(stable_collateral)}. "
                    "The dangerous move is ETH up, not ETH down."
                ),
                asset="ETH",
            )
        )

    chains_by_factor: dict[str, set[str]] = {}
    for position in analysis.positions:
        if position.type != "supply" or not position.usage_as_collateral:
            continue
        bucket = factor_bucket(position.asset)
        if bucket not in {"eth", "btc", "alt"}:
            continue
        chains_by_factor.setdefault(bucket, set()).add(position.chain)

    for bucket, chains in chains_by_factor.items():
        share = collateral_factors.get(bucket, ZERO)
        if len(chains) >= 2 and share >= Decimal("0.40"):
            names = ", ".join(sorted(chains))
            alerts.append(
                _alert(
                    id=f"correlation:cross-chain:{bucket}",
                    severity="info",
                    code="correlation_cross_chain",
                    title=f"{bucket.upper()} collateral is split across chains",
                    detail=(
                        f"{_pct(share)} of collateral is {bucket.upper()}-family, posted on {names}. "
                        "The price risk is one bet, with separate chain and bridge risk on top."
                    ),
                    asset=bucket.upper(),
                )
            )
    return alerts


def build_alerts(analysis: Analysis, extra: list[Alert] | None = None) -> list[Alert]:
    alerts = _health_alerts(analysis)
    if analysis.total_debt_usd > ZERO:
        alerts.extend(_share_alerts(analysis))
        alerts.extend(_correlation_alerts(analysis))
    if extra:
        alerts.extend(extra)
    alerts.sort(key=lambda alert: (SEVERITY_RANK.get(alert.severity, 9), alert.code, alert.title))
    return alerts
