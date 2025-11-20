export default function Toast({ message, tone = "info", onClose }) {
  if (!message) return null;
  const colors =
    tone === "warn"
      ? "bg-amber-900/60 border-amber-700 text-amber-100"
      : tone === "error"
      ? "bg-rose-900/60 border-rose-700 text-rose-100"
      : "bg-slate-900/70 border-slate-700 text-slate-100";
  return (
    <div className={`fixed bottom-4 right-4 px-4 py-3 rounded-xl border shadow-lg text-sm ${colors}`}>
      <div className="flex items-center gap-3">
        <span>{message}</span>
        <button
          onClick={onClose}
          className="text-xs px-2 py-1 rounded border border-slate-600 hover:bg-slate-800"
        >
          Close
        </button>
      </div>
    </div>
  );
}
