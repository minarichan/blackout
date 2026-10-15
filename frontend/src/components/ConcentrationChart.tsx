import { useState } from "react";
import { chainLabel, factorLabel, pct, usd } from "../format";
import type { Portfolio, Slice } from "../types";

type Book = "collateral" | "debt";

function Bars({ title, rows, label }: { title: string; rows: Slice[]; label?: (key: string) => string }) {
  const top = rows.slice(0, 5);
  return (
    <div>
      <p className="group-title">{title}</p>
      <div className="bars">
        {top.length === 0 ? <p className="muted">None</p> : null}
        {top.map((row) => (
          <div className="bar-row" key={row.key}>
            <span>{label ? label(row.key) : row.key}</span>
            <div className="track">
              <span style={{ width: `${Math.max(2, Math.min(100, row.share * 100))}%` }} />
            </div>
            <span className="num">
              {pct(row.share)} · {usd(row.value_usd)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ConcentrationChart({ concentration }: { concentration: Portfolio["concentration"] }) {
  const [book, setBook] = useState<Book>("collateral");
  const collateral = book === "collateral";
  const hhi = collateral ? concentration.collateral_hhi : concentration.debt_hhi;
  const topKey = collateral ? concentration.collateral_top_key : concentration.debt_top_key;
  const topShare = collateral ? concentration.collateral_top_share : concentration.debt_top_share;
  const factor = collateral ? concentration.collateral_by_factor : concentration.debt_by_factor;
  const asset = collateral ? concentration.collateral_by_asset : concentration.debt_by_asset;
  const protocol = collateral ? concentration.collateral_by_protocol : concentration.debt_by_protocol;
  const chain = collateral ? concentration.collateral_by_chain : concentration.debt_by_chain;

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Concentration</h2>
        <div className="seg" role="group" aria-label="Concentration side">
          <button type="button" className={collateral ? "active" : ""} onClick={() => setBook("collateral")}>
            Collateral
          </button>
          <button type="button" className={!collateral ? "active" : ""} onClick={() => setBook("debt")}>
            Debt
          </button>
        </div>
      </div>
      <p className="score-line">
        {topKey ? (
          <>
            <span className="num">{pct(topShare)}</span> in {topKey}
            <span className="muted"> · HHI {hhi.toFixed(2)}</span>
          </>
        ) : (
          <span className="muted">No {collateral ? "collateral" : "debt"} in this book.</span>
        )}
      </p>
      <p className="method">
        HHI is the sum of squared asset shares. 1.00 means one name. Protocol and chain shares are separate bets on the same dollars.
      </p>
      <Bars title="By factor" rows={factor} label={factorLabel} />
      <Bars title="By asset" rows={asset} />
      <Bars title="By protocol" rows={protocol} />
      <Bars title="By chain" rows={chain} label={chainLabel} />
    </section>
  );
}
