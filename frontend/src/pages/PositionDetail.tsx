import { Link, useParams } from "react-router-dom";
import { amount, hf, pct, price, priceSourceLabel, priceStatusLabel, primaryRiskLabel, riskClass, signedPct, usd } from "../format";
import type { Position } from "../types";
import { usePortfolio } from "../hooks/usePortfolio";

function priceNote(position: Position): string {
  if (position.price_source === "demo") {
    return "Fixture price. The demo book does not query Chainlink or CoinGecko.";
  }
  if (position.price_status === "fallback") {
    return `${priceSourceLabel(position.price_source)} filled a missing protocol price. Account health and liquidation distance include this substitute.`;
  }
  if (position.price_status === "divergent") {
    return "The protocol oracle disagrees with the reference. Liquidation math still uses the protocol price, because that is the figure liquidations use.";
  }
  if (position.price_status === "unpriced") {
    return "No protocol price and no reference. This leg is left out of dollar value, so the account health is incomplete.";
  }
  if (position.reference_price_usd === null) {
    return "No independent reference for this asset. Liquid staking tokens are not checked against spot ETH.";
  }
  return "The protocol oracle is inside the reference band. Health uses that oracle.";
}

export function PositionDetail() {
  const params = useParams();
  const positionId = params.positionId ? decodeURIComponent(params.positionId) : "";
  const { address, portfolio, loading, error } = usePortfolio();
  const position = portfolio?.positions.find((item) => item.id === positionId);
  const account = portfolio?.accounts.find((item) => item.account_key === position?.account_key);
  const siblings = portfolio?.positions.filter((item) => item.account_key === position?.account_key) ?? [];

  if (loading && !portfolio) return <p className="muted">Reading venues…</p>;
  if (error) return <p className="critical">{error}</p>;
  if (!position || !portfolio) {
    return (
      <section className="empty">
        <Link className="back" to={address ? `/book/${encodeURIComponent(address)}` : "/"}>
          Back to book
        </Link>
        <h1>Position not in this read.</h1>
      </section>
    );
  }

  return (
    <section>
      <Link className="back" to={`/book/${encodeURIComponent(address)}`}>
        Back to book
      </Link>
      <h1 className="detail-title">
        {position.asset} {position.type === "borrow" ? "borrow" : "supply"}
      </h1>
      <p className="identity">
        {position.chain_name} · {position.market_name} · {position.asset_address}
      </p>
      <div className="detail-grid">
        <article className="kpi">
          <span className="label">Value</span>
          <span className="value num">{usd(position.value_usd)}</span>
          <span className="hint">
            {amount(position.amount)} @ {price(position.price_usd)}
          </span>
        </article>
        <article className="kpi">
          <span className="label">Account health</span>
          <span className={`value num ${riskClass(position.health_factor)}`}>{hf(position.health_factor)}</span>
          <span className="hint">
            {account ? primaryRiskLabel(account.primary_risk) : "Account"}
            {position.price_status === "fallback" ? " · uses a fallback price" : ""}
          </span>
        </article>
        <article className="kpi">
          <span className="label">Isolated distance</span>
          <span className="value num">{pct(position.distance_to_liquidation_pct)}</span>
          <span className="hint">{usd(position.distance_to_liquidation_usd)} of room</span>
        </article>
        <article className="kpi">
          <span className="label">Liquidation price</span>
          <span className="value num">
            {position.liquidation_price === null ? "—" : position.liquidation_price === 0 ? "$0" : price(position.liquidation_price)}
          </span>
          <span className="hint">
            Threshold {position.liquidation_threshold ? pct(position.liquidation_threshold) : "—"}
          </span>
        </article>
      </div>
      <section className="panel">
        <h2>Price</h2>
        <div className="detail-grid">
          <article className="kpi">
            <span className="label">Used for health</span>
            <span className="value num">{price(position.price_usd)}</span>
            <span className="hint">
              {priceSourceLabel(position.price_source)}
              {position.price_status !== "protocol" ? ` · ${priceStatusLabel(position.price_status)}` : ""}
            </span>
          </article>
          <article className="kpi">
            <span className="label">Reference</span>
            <span className="value num">{position.reference_price_usd === null ? "—" : price(position.reference_price_usd)}</span>
            <span className="hint">{position.price_source === "demo" ? "Fixture book" : "Chainlink or $1 peg"}</span>
          </article>
          <article className="kpi">
            <span className="label">Gap</span>
            <span className={`value num ${position.price_status === "divergent" ? "high" : ""}`}>
              {signedPct(position.price_gap)}
            </span>
            <span className="hint">Protocol minus reference</span>
          </article>
        </div>
        <p className="method">{priceNote(position)}</p>
      </section>
      <section className="panel">
        <h2>Same account</h2>
        <p className="method">
          Liquidation price assumes every other price in this account stays put. Health is shared by the whole
          account.
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Side</th>
                <th className="num">Value</th>
                <th className="num">Distance</th>
              </tr>
            </thead>
            <tbody>
              {siblings.map((item) => (
                <tr key={item.id} className={item.id === position.id ? "selected" : ""}>
                  <td>{item.asset}</td>
                  <td>{item.type}</td>
                  <td className="num">{usd(item.value_usd)}</td>
                  <td className="num">{pct(item.distance_to_liquidation_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
