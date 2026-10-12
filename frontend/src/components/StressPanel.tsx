import type { StressScenario } from "../types";
import { hf, riskClass } from "../format";

export function StressPanel({ scenarios }: { scenarios: StressScenario[] }) {
  return (
    <section className="panel">
      <h2>Stress</h2>
      <div className="stress">
        {scenarios.map((scenario) => {
          const delta = scenario.health_factor_delta;
          const deltaText =
            delta === null ? "—" : `${delta > 0 ? "+" : ""}${delta.toFixed(3)} weighted health`;
          return (
            <div className="stress-row" key={scenario.id}>
              <strong>{scenario.label}</strong>
              <p>{scenario.description}</p>
              <span className={`num ${riskClass(scenario.worst_health_factor)}`}>
                worst {hf(scenario.worst_health_factor)}
              </span>
              <span className={scenario.any_liquidatable ? "critical" : "muted"}>
                {scenario.any_liquidatable ? "Liquidatable" : deltaText}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
