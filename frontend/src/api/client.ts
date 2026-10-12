import type { Portfolio, SnapshotPoint, WatchItem } from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      accept: "application/json",
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...init?.headers,
    },
    signal: AbortSignal.timeout(120_000),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getPortfolio(address: string, refresh = false): Promise<Portfolio> {
  const query = refresh ? "?refresh=true" : "";
  return request<Portfolio>(`/portfolio/${encodeURIComponent(address)}${query}`);
}

export function getHistory(address: string): Promise<SnapshotPoint[]> {
  return request<SnapshotPoint[]>(`/portfolio/${encodeURIComponent(address)}/history`);
}

export function getWatchlist(): Promise<WatchItem[]> {
  return request<WatchItem[]>("/watchlist");
}

export function saveWatch(address: string, label: string): Promise<WatchItem> {
  return request<WatchItem>("/watchlist", {
    method: "POST",
    body: JSON.stringify({ address, label }),
  });
}

export function deleteWatch(address: string): Promise<void> {
  return request<void>(`/watchlist/${encodeURIComponent(address)}`, { method: "DELETE" });
}
