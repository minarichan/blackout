import type { Slice } from "../types";
import { factorLabel, pct, usd } from "../format";

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

export function ConcentrationChart({
  collateralFactors,
  debtFactors,
  collateralAssets,
  collateralChains,
}: {
  collateralFactors: Slice[];
  debtFactors: Slice[];
  collateralAssets: Slice[];
  collateralChains: Slice[];
}) {
  return (
    <section className="panel">
      <h2>Concentration</h2>
      <Bars title="Collateral by factor" rows={collateralFactors} label={factorLabel} />
      <Bars title="Debt by factor" rows={debtFactors} label={factorLabel} />
      <Bars title="Collateral by asset" rows={collateralAssets} />
      <Bars title="Collateral by chain" rows={collateralChains} label={(key) => key[0].toUpperCase() + key.slice(1)} />
    </section>
  );
}
