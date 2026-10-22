export type Severity = "critical" | "high" | "elevated" | "info";

export type Slice = {
  key: string;
  value_usd: number;
  share: number;
};

export type Position = {
  id: string;
  user_address: string;
  chain: string;
  chain_name: string;
  protocol: string;
  protocol_name: string;
  market: string;
  market_name: string;
  account_key: string;
  type: "supply" | "borrow";
  asset: string;
  asset_address: string;
  amount: number;
  value_usd: number;
  price_usd: number;
  collateral_factor: number | null;
  liquidation_threshold: number | null;
  usage_as_collateral: boolean;
  health_factor: number | null;
  liquidation_price: number | null;
  distance_to_liquidation_pct: number | null;
  distance_to_liquidation_usd: number | null;
  entry_price: number | null;
  price_source: string;
  reference_price_usd: number | null;
  price_gap: number | null;
  price_status: "protocol" | "fallback" | "divergent" | "unpriced";
  metadata: Record<string, string | number | boolean | null>;
};

export type Account = {
  account_key: string;
  chain: string;
  chain_name: string;
  protocol: string;
  protocol_name: string;
  market: string;
  market_name: string;
  collateral_usd: number;
  supplied_usd: number;
  debt_usd: number;
  weighted_collateral_usd: number;
  health_factor: number | null;
  computed_health_factor: number | null;
  protocol_health_factor: number | null;
  protocol_liquidation_threshold: number | null;
  collateral_drawdown_pct: number | null;
  debt_increase_pct: number | null;
  primary_risk: string;
  primary_distance_pct: number | null;
  liquidatable: boolean;
  collateral_assets: string[];
  debt_assets: string[];
};

export type StressAccount = {
  account_key: string;
  chain: string;
  protocol_name: string;
  market_name: string;
  health_factor: number | null;
  liquidatable: boolean;
};

export type StressScenario = {
  id: string;
  label: string;
  description: string;
  portfolio_health_factor: number | null;
  worst_health_factor: number | null;
  health_factor_delta: number | null;
  any_liquidatable: boolean;
  accounts: StressAccount[];
};

export type Alert = {
  id: string;
  severity: Severity;
  code: string;
  title: string;
  detail: string;
  chain: string | null;
  protocol: string | null;
  asset: string | null;
  account_key: string | null;
};

export type Ingestion = {
  chain: string;
  protocol: string;
  ok: boolean;
  error: string | null;
  warning: string | null;
  position_count: number;
  elapsed_ms: number;
};

export type Summary = {
  total_supplied_usd: number;
  total_collateral_usd: number;
  total_debt_usd: number;
  net_usd: number;
  portfolio_health_factor: number | null;
  worst_health_factor: number | null;
  worst_account_key: string | null;
  primary_risk: string;
  primary_distance_pct: number | null;
  collateral_drawdown_pct: number | null;
  debt_increase_pct: number | null;
  account_count: number;
  position_count: number;
  alert_count: number;
};

export type SuggestedAction = {
  kind: "repay";
  account_key: string;
  chain: string;
  protocol_name: string;
  market_name: string;
  asset: string;
  amount: number;
  amount_usd: number;
  target_health: number;
  health_before: number;
  health_after: number | null;
  worst_before: number;
  worst_after: number | null;
  worst_after_account_key: string | null;
  worst_after_chain: string | null;
  worst_after_market_name: string | null;
};

export type Portfolio = {
  address: string;
  demo: boolean;
  data_quality: "live" | "partial" | "unavailable" | "demo";
  fetched_at: string;
  elapsed_ms: number;
  methodology: string;
  summary: Summary;
  positions: Position[];
  accounts: Account[];
  concentration: {
    collateral_by_asset: Slice[];
    collateral_by_protocol: Slice[];
    collateral_by_chain: Slice[];
    collateral_by_factor: Slice[];
    debt_by_asset: Slice[];
    debt_by_protocol: Slice[];
    debt_by_chain: Slice[];
    debt_by_factor: Slice[];
    collateral_hhi: number;
    debt_hhi: number;
    collateral_top_key: string;
    collateral_top_share: number;
    debt_top_key: string;
    debt_top_share: number;
  };
  stress: StressScenario[];
  alerts: Alert[];
  action: SuggestedAction | null;
  ingestion: Ingestion[];
};

export type SnapshotPoint = {
  timestamp: string;
  total_collateral_usd: number;
  total_debt_usd: number;
  portfolio_health_factor: number | null;
  worst_health_factor: number | null;
  alert_count: number;
};

export type WatchItem = {
  address: string;
  label: string;
  created_at: string;
};
