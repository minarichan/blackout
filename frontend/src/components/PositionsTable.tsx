import { Link } from "react-router-dom";
import type { Position } from "../types";
import { amount, chainLabel, distanceClass, hf, pct, price, priceStatusLabel, riskClass, usd } from "../format";

export function PositionsTable({
  address,
  positions,
  side,
  onSide,
}: {
  address: string;
  positions: Position[];
  side: "all" | "supply" | "borrow";
  onSide: (side: "all" | "supply" | "borrow") => void;
}) {
  const rows = positions.filter((position) => side === "all" || position.type === side);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Positions</h2>
        <div className="filters">
          <select value={side} onChange={(event) => onSide(event.target.value as "all" | "supply" | "borrow")}>
            <option value="all">All sides</option>
            <option value="supply">Supply</option>
            <option value="borrow">Borrow</option>
          </select>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Venue</th>
              <th className="num">Amount</th>
              <th className="num">Value</th>
              <th className="num">Health</th>
              <th className="num">Distance</th>
              <th className="num">Liq. price</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="muted">
                  No positions in this filter.
                </td>
              </tr>
            ) : (
              rows.map((position) => (
                <tr key={position.id}>
                  <td>
                    <Link to={`/book/${encodeURIComponent(address)}/position/${encodeURIComponent(position.id)}`}>
                      {position.asset}{" "}
                      <span className={`tag ${position.type}`}>{position.type === "borrow" ? "BORROW" : "SUPPLY"}</span>
                      <span className="sub">
                        {price(position.price_usd)}
                        {position.price_status !== "protocol" ? (
                          <span className={`tag ${position.price_status}`}>{priceStatusLabel(position.price_status)}</span>
                        ) : null}
                      </span>
                    </Link>
                  </td>
                  <td>
                    {position.protocol_name}
                    <span className="sub">
                      {chainLabel(position.chain)} · {position.market_name}
                    </span>
                  </td>
                  <td className="num">{amount(position.amount)}</td>
                  <td className="num">{usd(position.value_usd)}</td>
                  <td className={`num ${riskClass(position.health_factor)}`}>{hf(position.health_factor)}</td>
                  <td className={`num ${distanceClass(position.distance_to_liquidation_pct)}`}>
                    {pct(position.distance_to_liquidation_pct)}
                  </td>
                  <td className="num">
                    {position.liquidation_price === null ? "—" : position.liquidation_price === 0 ? "$0" : price(position.liquidation_price)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
