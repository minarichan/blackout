import { useMemo, useState } from "react";
import { AccountsPanel } from "../components/AccountsPanel";
import { AlertsPanel } from "../components/AlertsPanel";
import { ConcentrationChart } from "../components/ConcentrationChart";
import { PositionsTable } from "../components/PositionsTable";
import { RiskSummary } from "../components/RiskSummary";
import { StressPanel } from "../components/StressPanel";
import { chainLabel, shortAddress, when } from "../format";
import { usePortfolio } from "../hooks/usePortfolio";

export function Overview() {
  const { address, portfolio, history, loading, error } = usePortfolio();
  const [accountKey, setAccountKey] = useState<string | null>(null);
  const [side, setSide] = useState<"all" | "supply" | "borrow">("all");

  const positions = useMemo(() => {
    if (!portfolio) return [];
    return portfolio.positions.filter((position) => !accountKey || position.account_key === accountKey);
  }, [portfolio, accountKey]);

  if (!address) {
    return (
      <section className="empty">
        <h1>Risk first. Balances second.</h1>
        <p>
          Blackout reads Aave v3 and Compound v3 on Ethereum, Arbitrum, Base, and Optimism. It shows which
          lending account is closest to liquidation, how concentrated the collateral is, and what an ETH move
          does to health.
        </p>
        <p>Paste a wallet, or open the demo book. The demo is a constructed portfolio, not a live wallet.</p>
      </section>
    );
  }

  if (loading && !portfolio) {
    return (
      <section className="empty">
        <h1>Reading venues…</h1>
        <p>Querying Aave v3 and Compound v3 on Ethereum, Arbitrum, Base, and Optimism. The first read can take a while on public RPCs.</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="empty">
        <h1>This book did not load.</h1>
        <p>{error}</p>
      </section>
    );
  }

  if (!portfolio) return null;

  const failed = portfolio.ingestion.filter((item) => !item.ok);
  return (
    <>
      {portfolio.data_quality === "partial" ? (
        <div className="banner">
          Partial read. {failed.map((item) => `${chainLabel(item.chain)} ${item.protocol}: ${item.error}`).join(" · ")}
        </div>
      ) : null}
      {portfolio.data_quality === "unavailable" ? (
        <div className="banner bad">
          No venue responded. Check the RPC URLs, then retry. {failed.map((item) => item.error).filter(Boolean).join(" · ")}
        </div>
      ) : null}
      {portfolio.demo ? <div className="banner">Demo book. These positions are fixtures run through the live risk engine.</div> : null}
      {portfolio.ingestion.length > 0 ? (
        <div className="chips">
          {portfolio.ingestion.map((item) => (
            <span
              key={`${item.chain}-${item.protocol}`}
              className={`chip chain-${item.chain} ${item.ok ? (item.warning ? "warn" : "ok") : "bad"}`}
              title={item.error || item.warning || ""}
            >
              {chainLabel(item.chain)} {item.protocol === "aave-v3" ? "Aave" : "Compound"} · {item.position_count}
            </span>
          ))}
          <span className="chip">{loading ? "Refreshing…" : `Read ${when(portfolio.fetched_at)}`}</span>
        </div>
      ) : null}
      <header className="book-head">
        <p className="kicker">Cross-chain book</p>
        <h1>{address === "demo" ? "Demo book" : shortAddress(address)}</h1>
      </header>
      <RiskSummary summary={portfolio.summary} />
      <p className="method">{portfolio.methodology}</p>
      <div className="split">
        <AccountsPanel accounts={portfolio.accounts} selected={accountKey} onSelect={setAccountKey} />
        <AlertsPanel alerts={portfolio.alerts} />
      </div>
      <PositionsTable address={address} positions={positions} side={side} onSide={setSide} />
      <div className="bottom">
        <ConcentrationChart concentration={portfolio.concentration} />
        <StressPanel scenarios={portfolio.stress} />
      </div>
      {history.length > 0 ? (
        <section className="panel">
          <h2>Recent snapshots</h2>
          <div className="history">
            {history.slice(0, 8).map((point) => (
              <article key={point.timestamp}>
                <strong className="num">{point.worst_health_factor?.toFixed(3) ?? "—"}</strong>
                <span className="sub">{when(point.timestamp)}</span>
                <span className="sub">{point.alert_count} alerts</span>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
