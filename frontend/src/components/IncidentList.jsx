import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

const FAILURE_TYPES = ["spark_worker", "postgres", "kafka_lag", "schema_drift"];

const SEV_COLOR = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-blue-400",
};

const STATUS_COLOR = {
  running: "text-blue-400",
  awaiting_approval: "text-yellow-400 animate-pulse",
  completed: "text-green-400",
  error: "text-red-400",
};

export default function IncidentList({ activeIncident, setActiveIncident, onViewActivity }) {
  const qc = useQueryClient();
  const [simType, setSimType] = useState("spark_worker");

  const { data: incidents = [], isLoading } = useQuery({
    queryKey: ["incidents"],
    queryFn: api.getIncidents,
    refetchInterval: 5000,
  });

  const simulate = useMutation({
    mutationFn: api.simulateFailure,
    onSuccess: () => qc.invalidateQueries(["incidents"]),
  });

  const approve = useMutation({
    mutationFn: api.approve,
    onSuccess: () => qc.invalidateQueries(["incidents"]),
  });

  const reject = useMutation({
    mutationFn: api.reject,
    onSuccess: () => qc.invalidateQueries(["incidents"]),
  });

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-green-400 text-base font-bold">Incidents</h2>
        <div className="flex gap-2 ml-auto">
          <select
            value={simType}
            onChange={(e) => setSimType(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-300 text-xs rounded px-2 py-1"
          >
            {FAILURE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
          <button
            onClick={() => simulate.mutate(simType)}
            disabled={simulate.isPending}
            className="bg-red-800 hover:bg-red-700 text-white text-xs px-3 py-1 rounded"
          >
            {simulate.isPending ? "Injecting…" : "Inject Failure"}
          </button>
        </div>
      </div>

      {isLoading && <p className="text-gray-500">Loading …</p>}

      {incidents.length === 0 && !isLoading && (
        <p className="text-gray-600">No incidents yet. Inject a failure to start.</p>
      )}

      <div className="space-y-3">
        {incidents.map((inc) => {
          const st = inc.state || {};
          const isActive = inc.incident_id === activeIncident;
          return (
            <div
              key={inc.incident_id}
              onClick={() => setActiveIncident(inc.incident_id)}
              className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                isActive
                  ? "border-green-600 bg-gray-900"
                  : "border-gray-800 bg-gray-900 hover:border-gray-700"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="text-green-300 font-bold">{inc.incident_id}</span>
                  <span className="text-gray-600 mx-2">·</span>
                  <span className={SEV_COLOR[st.severity] ?? "text-gray-400"}>
                    {st.severity?.toUpperCase() || "—"}
                  </span>
                  <span className="text-gray-600 mx-2">·</span>
                  <span className="text-gray-400">{st.service || "detecting…"}</span>
                </div>
                <span className={`text-xs ${STATUS_COLOR[inc.status] ?? "text-gray-500"}`}>
                  {inc.status?.replace("_", " ").toUpperCase()}
                </span>
              </div>

              {st.category && (
                <div className="mt-1 text-xs text-gray-500">
                  Category: <span className="text-gray-300">{st.category}</span>
                </div>
              )}
              {st.root_cause && (
                <div className="mt-1 text-xs text-gray-500 truncate">
                  Root cause: <span className="text-gray-300">{st.root_cause}</span>
                </div>
              )}

              {/* Approval buttons */}
              {inc.status === "awaiting_approval" && (
                <div
                  className="mt-3 flex gap-3"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="text-xs text-yellow-400 mr-2">
                    Awaiting approval:&nbsp;
                    <span className="text-gray-300">{st.proposed_action || st.proposed_command}</span>
                    {st.solution_source === "web" && (
                      <span className="ml-2 text-orange-400">[WEB SOURCE — ALWAYS HITL]</span>
                    )}
                  </div>
                  <button
                    onClick={() => approve.mutate(inc.incident_id)}
                    disabled={approve.isPending}
                    className="bg-green-700 hover:bg-green-600 text-white text-xs px-3 py-1 rounded"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => reject.mutate(inc.incident_id)}
                    disabled={reject.isPending}
                    className="bg-red-700 hover:bg-red-600 text-white text-xs px-3 py-1 rounded"
                  >
                    Reject
                  </button>
                </div>
              )}

              <div className="mt-2 flex gap-4 text-xs text-gray-600">
                <span>Detected: {st.detected_at?.slice(0, 19).replace("T", " ") || "—"}</span>
                <button
                  className="text-blue-500 hover:text-blue-400 underline"
                  onClick={(e) => { e.stopPropagation(); setActiveIncident(inc.incident_id); onViewActivity(); }}
                >
                  View Agent Trace
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
