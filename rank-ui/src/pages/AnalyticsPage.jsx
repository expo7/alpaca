import { useEffect, useMemo, useState } from "react";

const RANGE_OPTIONS = [7, 30, 90];

const EVENT_LABELS = {
  ranking_run: "Ranking runs",
  registration: "Registrations",
  chart_opened: "Charts opened",
  explanation_opened: "Explanations opened",
  watchlist_add: "Watchlist additions",
};

function MetricCard({ label, value, detail }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-bold text-slate-100">{value ?? 0}</div>
      {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}

function EmptyRows({ children }) {
  return <div className="py-8 text-center text-sm text-slate-500">{children}</div>;
}

export default function AnalyticsPage({ token, isStaff }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || !isStaff) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    fetch(`/api/analytics/summary/?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload?.detail || "Unable to load analytics.");
        return payload;
      })
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((err) => {
        if (active) setError(err.message || "Unable to load analytics.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [days, isStaff, token]);

  const maxDailyViews = useMemo(
    () => Math.max(1, ...(data?.daily || []).map((row) => row.page_views)),
    [data]
  );
  const tradeRecordTraffic = useMemo(
    () => (data?.top_pages || []).find((row) => row.path === "/signals") || { views: 0, visitors: 0 },
    [data]
  );

  if (!isStaff) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <h1 className="text-xl font-semibold">Analytics is private</h1>
          <p className="mt-2 text-sm text-slate-400">Sign in with a staff account to view site activity.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-300">Private report</div>
          <h1 className="mt-1 text-2xl font-bold text-slate-100">Site analytics</h1>
          <p className="mt-1 text-sm text-slate-400">Known bots are filtered. Visitor counts are approximate, and raw IP addresses are never stored.</p>
        </div>
        <div className="flex gap-2" aria-label="Analytics date range">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`rounded-full border px-3 py-1.5 text-sm ${days === option ? "border-indigo-500 bg-indigo-600 text-white" : "border-slate-700 bg-slate-900 text-slate-300"}`}
            >
              {option} days
            </button>
          ))}
        </div>
      </header>

      {loading && <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8 text-center text-slate-400">Loading activity…</div>}
      {error && <div className="rounded-2xl border border-rose-800 bg-rose-950/30 p-4 text-sm text-rose-200">{error}</div>}

      {!loading && !error && data && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <MetricCard label="Visitors" value={data.totals?.visitors} detail={`Unique in ${days} days`} />
            <MetricCard label="Page views" value={data.totals?.page_views} />
            <MetricCard label="Article reads" value={data.totals?.article_views} />
            <MetricCard
              label="Trade Record views"
              value={tradeRecordTraffic.views}
              detail={`${tradeRecordTraffic.visitors} unique ${tradeRecordTraffic.visitors === 1 ? "visitor" : "visitors"}`}
            />
            <MetricCard label="Ranking runs" value={data.totals?.ranking_runs} />
            <MetricCard label="Registrations" value={data.totals?.registrations} />
          </section>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
            <div className="mb-4">
              <h2 className="font-semibold text-slate-100">Daily traffic</h2>
              <p className="text-sm text-slate-400">Views and unique visitors recorded by day.</p>
            </div>
            {(data.daily || []).length ? (
              <div className="space-y-2">
                {data.daily.map((row) => (
                  <div key={row.date} className="grid grid-cols-[6rem_1fr_auto] items-center gap-3 text-sm">
                    <span className="text-slate-400">{new Date(`${row.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                    <div className="h-3 overflow-hidden rounded-full bg-slate-800">
                      <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(4, (row.page_views / maxDailyViews) * 100)}%` }} />
                    </div>
                    <span className="min-w-24 text-right text-slate-300">{row.page_views} views · {row.visitors} visitors</span>
                  </div>
                ))}
              </div>
            ) : <EmptyRows>No activity recorded yet.</EmptyRows>}
          </section>

          <div className="grid gap-5 lg:grid-cols-2">
            <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
              <h2 className="font-semibold text-slate-100">Most-viewed pages</h2>
              <div className="mt-3 divide-y divide-slate-800">
                {(data.top_pages || []).map((row) => (
                  <div key={row.path} className="flex items-start justify-between gap-3 py-3 text-sm">
                    <span className="break-all text-slate-300">{row.path}</span>
                    <span className="shrink-0 text-slate-400">{row.views} views · {row.visitors} visitors</span>
                  </div>
                ))}
                {!(data.top_pages || []).length && <EmptyRows>No pages recorded yet.</EmptyRows>}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
              <h2 className="font-semibold text-slate-100">Traffic sources</h2>
              <div className="mt-3 divide-y divide-slate-800">
                {(data.referrers || []).map((row) => (
                  <div key={row.referrer_host} className="flex justify-between gap-3 py-3 text-sm">
                    <span className="text-slate-300">{row.referrer_host}</span>
                    <span className="text-slate-400">{row.visitors} visitors</span>
                  </div>
                ))}
                {!(data.referrers || []).length && <EmptyRows>No external referrals recorded yet.</EmptyRows>}
              </div>
            </section>
          </div>

          <section className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
            <h2 className="font-semibold text-slate-100">Product activity</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(data.events || []).map((row) => (
                <div key={row.event_name} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <div className="text-sm text-slate-400">{EVENT_LABELS[row.event_name] || row.event_name.replaceAll("_", " ")}</div>
                  <div className="mt-1 text-2xl font-semibold text-slate-100">{row.count}</div>
                  <div className="text-xs text-slate-500">{row.visitors} visitors</div>
                </div>
              ))}
              {!(data.events || []).length && <EmptyRows>No product actions recorded yet.</EmptyRows>}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
