import React, { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, createEventSource } from "../api/client";

const NODE_COLOR = {
  monitoring_agent: "text-blue-400",
  triage_agent: "text-purple-400",
  rca_agent: "text-orange-400",
  lineage_agent: "text-yellow-400",
  runbook_agent: "text-cyan-400",
  remediation_agent: "text-red-400",
  execute_remediation: "text-red-300",
  validation_agent: "text-green-400",
  postmortem_agent: "text-pink-400",
  escalation: "text-red-500",
};

export default function AgentActivity({ incidentId }) {
  const [liveEvents, setLiveEvents] = useState([]);
  const bottomRef = useRef(null);

  const { data: incident } = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => api.getIncident(incidentId),
    enabled: !!incidentId,
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (!incidentId) return;
    setLiveEvents([]);
    const es = createEventSource(
      incidentId,
      (event) => {
        if (event.type !== "ping") {
          setLiveEvents((prev) => [...prev, event]);
        }
      },
      () => {}
    );
    return () => es.close();
  }, [incidentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveEvents]);

  if (!incidentId) {
    return (
      <div className="text-gray-600">
        Select an incident from the Incidents tab to view its agent trace.
      </div>
    );
  }

  const timeline = incident?.state?.timeline || [];

  return (
    <div>
      <h2 className="text-green-400 text-base font-bold mb-1">Agent Activity</h2>
      <div className="text-xs text-gray-500 mb-4">
        Incident: <span className="text-green-300">{incidentId}</span>
        {incident?.status && (
          <span className="ml-3 text-gray-400">
            Status: <span className="text-yellow-300">{incident.status}</span>
          </span>
        )}
      </div>

      {/* Reasoning summary (latest) */}
      {incident?.state?.root_cause && (
        <div className="mb-4 bg-gray-900 border border-gray-800 rounded p-3 text-xs space-y-1">
          <div>
            <span className="text-gray-500">Root Cause: </span>
            <span className="text-orange-300">{incident.state.root_cause}</span>
          </div>
          {incident.state.confidence_score > 0 && (
            <div>
              <span className="text-gray-500">Confidence: </span>
              <span className="text-white">
                {(incident.state.confidence_score * 100).toFixed(0)}%
              </span>
            </div>
          )}
          {incident.state.evidence_used?.length > 0 && (
            <div>
              <span className="text-gray-500">Evidence: </span>
              <span className="text-gray-300">
                {incident.state.evidence_used.slice(0, 3).join(" · ")}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Timeline feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-xs space-y-2">
        {timeline.length === 0 && liveEvents.length === 0 && (
          <span className="text-gray-600">Waiting for agent events…</span>
        )}

        {/* Stored timeline events */}
        {timeline.map((ev, i) => (
          <div key={`tl-${i}`} className="flex gap-3">
            <span className="text-gray-600 shrink-0">
              {ev.timestamp?.slice(11, 19) || "??:??:??"}
            </span>
            <span className={NODE_COLOR[ev.agent] ?? "text-gray-400"}>
              [{ev.agent}]
            </span>
            <span className="text-gray-300">{ev.action}</span>
            <span className="text-gray-500 truncate">{ev.details}</span>
          </div>
        ))}

        {/* Live SSE events (node_complete, awaiting_approval, etc.) */}
        {liveEvents.map((ev, i) => (
          <div key={`live-${i}`} className="flex gap-3">
            <span className="text-gray-600 shrink-0">
              {ev.data?.timestamp?.slice(11, 19) || "LIVE"}
            </span>
            <span className={NODE_COLOR[ev.data?.node] ?? "text-cyan-600"}>
              [{ev.type}]
            </span>
            <span className="text-gray-300">
              {ev.data?.node || ""}
            </span>
            {ev.type === "awaiting_approval" && (
              <span className="text-yellow-400">
                ⚠ PENDING APPROVAL: {ev.data?.proposed_action}
                {ev.data?.solution_source === "web" && " [WEB — always HITL]"}
              </span>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
