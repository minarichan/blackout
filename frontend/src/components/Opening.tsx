import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { hf } from "../format";

const STILL = [
  { chain: "ethereum", name: "Ethereum", health: 2.4 },
  { chain: "base", name: "Base", health: 1.81 },
  { chain: "optimism", name: "Optimism", health: 2.15 },
];

const START = 2.1;
const END = 0.94;
const DRIFT_MS = 12000;
const HOLD_MS = 1600;
const SCALE = 2.5;

function movingHealth(elapsed: number): number {
  const loop = DRIFT_MS + HOLD_MS;
  const t = elapsed % loop;
  if (t >= DRIFT_MS) return END;
  return START + (END - START) * (t / DRIFT_MS);
}

function tone(health: number): string {
  if (health < 1.05) return "critical";
  if (health < 1.2) return "high";
  if (health < 1.5) return "elevated";
  return "safe";
}

function isWallet(value: string): boolean {
  return /^0x[a-fA-F0-9]{40}$/.test(value.trim());
}

export function Opening() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    if (reduced) return;
    let frame = 0;
    const started = performance.now();
    const tick = (now: number) => {
      setElapsed(now - started);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [reduced]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = draft.trim();
    if (!isWallet(next)) return;
    navigate(`/book/${encodeURIComponent(next)}`);
  }

  const live = reduced ? 1.18 : movingHealth(elapsed);
  const liquidatable = live < 1;
  const accounts = [
    STILL[0],
    { chain: "arbitrum", name: "Arbitrum", health: live },
    STILL[1],
    STILL[2],
  ];

  return (
    <section className="landing">
      <header className="landing-nav">
        <Link className="brand" to="/">
          <span className="mark" aria-hidden="true" />
          <span className="brand-copy">
            <strong>Blackout</strong>
          </span>
        </Link>
        <nav>
          <span>Health</span>
          <span>Concentration</span>
          <span>Stress</span>
        </nav>
        <button type="button" className="landing-link" onClick={() => navigate("/book/demo")}>
          Demo book
        </button>
      </header>

      <div className="landing-stage">
        <div className="landing-copy">
          <h1>
            Risk
            <br />
            first.
            <br />
            One account
            <br />
            can fail.
          </h1>
          <div className="landing-actions">
            <form onSubmit={submit}>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="0x wallet address"
                aria-label="Wallet address"
                spellCheck={false}
              />
              <button type="submit" disabled={!isWallet(draft)}>
                Open
              </button>
            </form>
            <button type="button" className="landing-link" onClick={() => navigate("/book/demo")}>
              <i aria-hidden="true" />
              Demo book
            </button>
          </div>
        </div>

        <div className="landing-panels">
          <div className="landing-icons" aria-hidden="true">
            <span className="chain-ethereum" />
            <span className="chain-arbitrum" />
            <span className="chain-base" />
            <span className="chain-optimism" />
          </div>
          <div className="glass glass-book">
            {accounts.map((account) => (
              <div className="hf-row" key={account.chain}>
                <span className={`chip chain-${account.chain}`}>{account.name}</span>
                <span className="hf-track">
                  <span className={tone(account.health)} style={{ width: `${(Math.min(account.health, SCALE) / SCALE) * 100}%` }} />
                  <i style={{ left: `${(1 / SCALE) * 100}%` }} />
                </span>
                <span className={`hf-num ${tone(account.health)}`}>
                  {account.chain === "arbitrum" && liquidatable ? "Liquidatable" : hf(account.health)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
