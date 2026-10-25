const usdFormat = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const usdExact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

export function usd(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}$${(abs / 1_000).toFixed(1)}k`;
  if (abs >= 1_000) return usdFormat.format(value);
  return usdExact.format(value);
}

export function hf(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(2);
  return value.toFixed(3);
}

export function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function signedPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const text = pct(Math.abs(value));
  if (value > 0) return `+${text}`;
  if (value < 0) return `-${text}`;
  return text;
}

export function priceSourceLabel(value: string): string {
  switch (value) {
    case "aave_oracle":
      return "Aave oracle";
    case "compound_oracle":
      return "Compound oracle";
    case "chainlink":
      return "Chainlink";
    case "coingecko":
      return "CoinGecko";
    case "demo":
      return "Fixture";
    default:
      return value;
  }
}

export function priceStatusLabel(value: string): string {
  switch (value) {
    case "fallback":
      return "Fallback";
    case "divergent":
      return "Divergent";
    case "unpriced":
      return "Unpriced";
    default:
      return "Protocol";
  }
}

export function eth(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value === 0) return "0 ETH";
  if (value < 0.0001) return `${value.toExponential(2)} ETH`;
  return `${value.toLocaleString("en-US", { maximumFractionDigits: 6 })} ETH`;
}

export function gasUnits(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

export function amount(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (abs >= 1) return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

export function price(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "—";
  if (value >= 1000) return usdFormat.format(value);
  if (value >= 1) return `$${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 4 })}`;
}

export function shortAddress(value: string): string {
  if (value === "demo") return "Demo book";
  if (value.length < 12) return value;
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

export function riskClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "muted";
  if (value < 1.05) return "critical";
  if (value < 1.2) return "high";
  if (value < 1.5) return "elevated";
  return "safe";
}

export function distanceClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return "muted";
  if (value < 0.05) return "critical";
  if (value < 0.1) return "high";
  if (value < 0.2) return "elevated";
  return "safe";
}

export function primaryRiskLabel(value: string): string {
  switch (value) {
    case "collateral_drawdown":
      return "Collateral drawdown";
    case "debt_expansion":
      return "Debt expansion";
    case "mixed":
      return "Mixed move";
    default:
      return "No open debt";
  }
}

export function factorLabel(value: string): string {
  switch (value) {
    case "eth":
      return "ETH";
    case "btc":
      return "BTC";
    case "usdc":
      return "USDC";
    case "stable":
      return "Stables";
    case "soft_stable":
      return "Soft stables";
    case "alt":
      return "Alts";
    default:
      return value;
  }
}

export function chainLabel(value: string): string {
  switch (value) {
    case "ethereum":
      return "Ethereum";
    case "arbitrum":
      return "Arbitrum";
    case "base":
      return "Base";
    case "optimism":
      return "Optimism";
    default:
      return value;
  }
}

export function when(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
