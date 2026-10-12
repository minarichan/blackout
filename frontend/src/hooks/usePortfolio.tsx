import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { deleteWatch, getHistory, getPortfolio, getWatchlist, saveWatch } from "../api/client";
import type { Portfolio, SnapshotPoint, WatchItem } from "../types";

type PortfolioContextValue = {
  address: string;
  portfolio: Portfolio | null;
  history: SnapshotPoint[];
  watchlist: WatchItem[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  remember: (label: string) => Promise<void>;
  forget: (address: string) => Promise<void>;
};

const PortfolioContext = createContext<PortfolioContextValue | null>(null);

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const matched = location.pathname.match(/^\/book\/([^/]+)/);
  const address = matched ? decodeURIComponent(matched[1]) : "";
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [history, setHistory] = useState<SnapshotPoint[]>([]);
  const [watchlist, setWatchlist] = useState<WatchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getWatchlist()
      .then((rows) => {
        if (!cancelled) setWatchlist(rows);
      })
      .catch(() => {
        if (!cancelled) setWatchlist([]);
      });
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  useEffect(() => {
    if (!address) {
      setPortfolio(null);
      setHistory([]);
      setError(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const sameBook = portfolio?.address === address;
    if (!sameBook) setPortfolio(null);
    getPortfolio(address, nonce > 0 && sameBook)
      .then(async (book) => {
        if (cancelled) return;
        setPortfolio(book);
        const points = await getHistory(address).catch(() => []);
        if (!cancelled) setHistory(points);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setPortfolio(null);
        setError(reason instanceof Error ? reason.message : "Could not load this book.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [address, nonce]);

  async function remember(label: string) {
    if (!address) return;
    const saved = await saveWatch(address, label);
    setWatchlist((current) => [saved, ...current.filter((item) => item.address !== saved.address)]);
  }

  async function forget(target: string) {
    await deleteWatch(target);
    setWatchlist((current) => current.filter((item) => item.address !== target));
  }

  return (
    <PortfolioContext.Provider
      value={{
        address,
        portfolio,
        history,
        watchlist,
        loading,
        error,
        refresh: () => setNonce((value) => value + 1),
        remember,
        forget,
      }}
    >
      {children}
    </PortfolioContext.Provider>
  );
}

export function usePortfolio(): PortfolioContextValue {
  const value = useContext(PortfolioContext);
  if (!value) throw new Error("Portfolio context is missing.");
  return value;
}
