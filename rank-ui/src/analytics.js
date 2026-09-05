export function trackEvent(eventName, { path, metadata } = {}) {
  if (navigator.doNotTrack === "1") return;
  const payload = JSON.stringify({
    event_name: eventName,
    path: path || window.location.pathname,
    referrer: document.referrer || "",
    metadata: metadata || {},
  });

  const accessToken = localStorage.getItem("access");
  const headers = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  fetch("/api/analytics/events/", {
    method: "POST",
    headers,
    body: payload,
    keepalive: true,
  }).catch(() => {
    // Analytics must never interrupt the product experience.
  });
}
