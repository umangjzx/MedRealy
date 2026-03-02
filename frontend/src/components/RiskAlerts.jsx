const severityColors = {
  HIGH: 'bg-red-500/10 border-red-500/40 text-red-200',
  MEDIUM: 'bg-yellow-500/10 border-yellow-500/40 text-yellow-200',
  LOW: 'bg-blue-500/10 border-blue-500/40 text-blue-200',
};

export default function RiskAlerts({ alerts }) {
  return (
    <div className="mt-6 glass rounded-xl p-5 sm:p-6">
      <h3 className="text-xl font-semibold mb-2">Risk Alerts</h3>
      {!alerts?.length ? (
        <p className="text-sm text-slate-400">✅ No risk alerts identified.</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert, idx) => (
            <div key={idx} className={`p-3 rounded-lg border ${severityColors[alert.severity] ?? 'bg-slate-900 border-slate-500 text-slate-200'}`}>
              <div className="flex items-start justify-between gap-3">
                <p>
                  <span className="font-bold uppercase">{alert.severity}</span>: {alert.description}{" "}
                  <span className="text-sm opacity-80">({alert.category})</span>
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}