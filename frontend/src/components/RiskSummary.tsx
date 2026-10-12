import type { Summary } from "../types";
import { distanceClass, hf, pct, primaryRiskLabel, riskClass, usd } from "../format";

export function RiskSummary({ summary }: { summary: Summary }) {
  const distanceKind = primaryRiskLabel(summary.primary_risk);
  return (
    <section className="kpis">
      <article className="kpi">
        <span className="label">Worst health</span>
        <span className={`value num ${riskClass(summary.worst_health_factor)}`}>{hf(summary.worst_health_factor)}</span>
        <span className="hint">First account to liquidate</span>
      </article>
      <article className="kpi">
        <span className="label">Weighted health</span>
        <span className={`value num ${riskClass(summary.portfolio_health_factor)}`}>
          {hf(summary.portfolio_health_factor)}
        </span>
        <span className="hint">Weighted by debt, not margin</span>
      </article>
      <article className="kpi">
        <span className="label">Collateral</span>
        <span className="value num">{usd(summary.total_collateral_usd)}</span>
        <span className="hint">Counts toward health</span>
      </article>
      <article className="kpi">
        <span className="label">Debt</span>
        <span className="value num">{usd(summary.total_debt_usd)}</span>
        <span className="hint">Net equity {usd(summary.net_usd)}</span>
      </article>
      <article className="kpi">
        <span className="label">Nearest room</span>
        <span className={`value num ${distanceClass(summary.primary_distance_pct)}`}>
          {pct(summary.primary_distance_pct)}
        </span>
        <span className="hint">{distanceKind}</span>
      </article>
      <article className="kpi">
        <span className="label">Alerts</span>
        <span className={`value num ${summary.alert_count ? "elevated" : "safe"}`}>{summary.alert_count}</span>
        <span className="hint">
          {summary.account_count} accounts · {summary.position_count} legs
        </span>
      </article>
    </section>
  );
}
