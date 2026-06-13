const BASE = import.meta.env.VITE_API_URL || "/api";

export async function fetchJSON(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  getSystemHealth: () => fetchJSON("/system_health"),
  getIncidents: () => fetchJSON("/incidents"),
  getIncident: (id) => fetchJSON(`/incident/${id}`),
  getReport: (id) => fetchJSON(`/report/${id}`),
  simulateFailure: (failure_type) =>
    fetchJSON("/simulate_failure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ failure_type }),
    }),
  approve: (id) => fetchJSON(`/incident/${id}/approve`, { method: "POST" }),
  reject: (id) => fetchJSON(`/incident/${id}/reject`, { method: "POST" }),
};

export function createEventSource(incidentId, onEvent, onError) {
  const es = new EventSource(`${BASE}/stream/${incidentId}`);
  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch (_) {}
  };
  es.onerror = onError;
  return es;
}
