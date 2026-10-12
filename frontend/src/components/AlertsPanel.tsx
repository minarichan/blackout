import type { Alert } from "../types";

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="panel">
      <h2>Alerts</h2>
      {alerts.length === 0 ? (
        <p className="muted">No threshold breaks on this book.</p>
      ) : (
        <div className="alerts">
          {alerts.map((alert) => (
            <article key={alert.id} className={`alert ${alert.severity}`}>
              <strong>{alert.title}</strong>
              <p>{alert.detail}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
