import type { SuggestedAction } from "../types";
import { amount, chainLabel, hf, usd } from "../format";

export function ActionPanel({ action }: { action: SuggestedAction | null }) {
  if (!action) {
    return (
      <section className="panel action">
        <h2>Suggested repay</h2>
        <p className="method">
          No repay. The worst account is already above a 1.50 health buffer, or one repay would leave another
          account just as close to liquidation. Withdrawing collateral would lower health, so it is not suggested.
          Nothing is sent.
        </p>
      </section>
    );
  }

  const sameAccount = action.worst_after_account_key === action.account_key;
  const afterBook =
    action.worst_after === null
      ? "the book would have no open debt"
      : sameAccount
        ? `this account would still be the tightest, at ${hf(action.worst_after)}`
        : `${action.worst_after_market_name} on ${chainLabel(action.worst_after_chain ?? "")} would be the tightest, at ${hf(action.worst_after)}`;

  return (
    <section className="panel action">
      <div className="panel-head">
        <h2>Suggested repay</h2>
        <span className="tag">Not sent</span>
      </div>
      <p className="score-line">
        Repay {amount(action.amount)} {action.asset}
        <span className="muted"> · {usd(action.amount_usd)}</span>
      </p>
      <p className="method">
        {action.market_name} on {chainLabel(action.chain)}. Health on this account goes from {hf(action.health_before)} to{" "}
        {action.health_after === null ? "no debt" : hf(action.health_after)}, which is the {hf(action.target_health)} buffer.
        After that, {afterBook}. Withdrawing collateral would lower health, so the move is a repay. Nothing is sent.
      </p>
    </section>
  );
}
