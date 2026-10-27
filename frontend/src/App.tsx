import { FormEvent, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { Opening } from "./components/Opening";
import { shortAddress } from "./format";
import { PortfolioProvider, usePortfolio } from "./hooks/usePortfolio";

function isWallet(value: string): boolean {
  return value.toLowerCase() === "demo" || /^0x[a-fA-F0-9]{40}$/.test(value.trim());
}

function Shell() {
  const navigate = useNavigate();
  const { address, loading, watchlist, refresh, remember, forget } = usePortfolio();
  const [draft, setDraft] = useState("");
  const [label, setLabel] = useState("");

  useEffect(() => {
    if (!address || address === "demo") return;
    setDraft(address);
  }, [address]);

  if (!address) return <Opening />;

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = draft.trim();
    if (!isWallet(next)) return;
    navigate(`/book/${encodeURIComponent(next)}`);
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand" to="/">
          <span className="mark" aria-hidden="true" />
          <span className="brand-copy">
            <strong>Blackout</strong>
            <span>Position & risk</span>
          </span>
        </Link>
        <div className="side-block">
          <p className="side-label">Book</p>
          <NavLink className={({ isActive }) => `watch-item ${isActive ? "active" : ""}`} to="/book/demo">
            <span>Demo book</span>
            <small>Fixture</small>
          </NavLink>
        </div>
        <div className="side-block">
          <p className="side-label">Watchlist</p>
          <div className="watch-list">
            {watchlist.length === 0 ? <span className="muted">None saved</span> : null}
            {watchlist.map((item) => (
              <div key={item.address} className={`watch-item ${item.address === address ? "active" : ""}`}>
                <button type="button" className="text-button" onClick={() => navigate(`/book/${encodeURIComponent(item.address)}`)}>
                  {item.label || shortAddress(item.address)}
                </button>
                <button type="button" className="text-button" onClick={() => void forget(item.address)} aria-label="Remove">
                  ×
                </button>
              </div>
            ))}
          </div>
          {address ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void remember(label || shortAddress(address));
                setLabel("");
              }}
            >
              <input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="Label this address"
                aria-label="Watchlist label"
                style={{ width: "100%", marginBottom: 8 }}
              />
              <button className="ghost" type="submit">
                Save to watchlist
              </button>
            </form>
          ) : null}
        </div>
        <p className="side-note">Aave v3 and Compound v3. Ethereum, Arbitrum, Base, Optimism. Read only.</p>
      </aside>
      <main className="main">
        <div className="toolbar">
          <form onSubmit={submit}>
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="0x wallet address"
              aria-label="Wallet address"
              spellCheck={false}
            />
            <button className="primary" type="submit" disabled={loading || !isWallet(draft)}>
              Load
            </button>
          </form>
          <button className="ghost" type="button" onClick={() => navigate("/book/demo")}>
            Demo book
          </button>
          <button className="ghost" type="button" onClick={refresh} disabled={!address || loading}>
            {loading ? "Reading…" : "Refresh"}
          </button>
        </div>
        <Outlet />
      </main>
    </div>
  );
}

export function App() {
  return (
    <PortfolioProvider>
      <Shell />
    </PortfolioProvider>
  );
}
