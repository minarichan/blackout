import type { Account } from "../types";
import { chainLabel, hf, pct, primaryRiskLabel, riskClass, usd } from "../format";

export function AccountsPanel({
  accounts,
  selected,
  onSelect,
}: {
  accounts: Account[];
  selected: string | null;
  onSelect: (accountKey: string | null) => void;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Lending accounts</h2>
        {selected ? (
          <button className="text-button" type="button" onClick={() => onSelect(null)}>
            Clear filter
          </button>
        ) : null}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Account</th>
              <th className="num">Collateral</th>
              <th className="num">Debt</th>
              <th className="num">Health</th>
              <th className="num">Room</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => (
              <tr
                key={account.account_key}
                className={`clickable ${selected === account.account_key ? "selected" : ""}`}
                onClick={() => onSelect(selected === account.account_key ? null : account.account_key)}
              >
                <td>
                  {account.market_name}
                  <span className="sub">
                    {chainLabel(account.chain)} · {primaryRiskLabel(account.primary_risk)}
                  </span>
                </td>
                <td className="num">{usd(account.collateral_usd)}</td>
                <td className="num">{usd(account.debt_usd)}</td>
                <td className={`num ${riskClass(account.health_factor)}`}>{hf(account.health_factor)}</td>
                <td className="num">{pct(account.primary_distance_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
