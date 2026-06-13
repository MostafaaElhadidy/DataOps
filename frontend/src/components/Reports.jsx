import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { api } from "../api/client";

export default function Reports() {
  const [selectedId, setSelectedId] = useState(null);

  const { data: incidents = [] } = useQuery({
    queryKey: ["incidents"],
    queryFn: api.getIncidents,
    refetchInterval: 10000,
  });

  const completed = incidents.filter(
    (inc) => inc.status === "completed" && inc.state?.report_path
  );

  const { data: report, isLoading } = useQuery({
    queryKey: ["report", selectedId],
    queryFn: () => api.getReport(selectedId),
    enabled: !!selectedId,
  });

  return (
    <div className="flex gap-6 h-full">
      {/* Sidebar */}
      <div className="w-64 shrink-0">
        <h2 className="text-green-400 text-base font-bold mb-4">Postmortem Reports</h2>
        {completed.length === 0 && (
          <p className="text-gray-600 text-xs">No reports yet.</p>
        )}
        <div className="space-y-2">
          {completed.map((inc) => (
            <button
              key={inc.incident_id}
              onClick={() => setSelectedId(inc.incident_id)}
              className={`w-full text-left text-xs p-2 rounded border transition-colors ${
                selectedId === inc.incident_id
                  ? "border-green-600 bg-gray-900 text-green-300"
                  : "border-gray-800 bg-gray-900 text-gray-400 hover:border-gray-700"
              }`}
            >
              <div className="font-bold">{inc.incident_id}</div>
              <div className="text-gray-500">
                {inc.state?.service} · {inc.state?.severity}
              </div>
              <div className="text-gray-600">
                {inc.state?.detected_at?.slice(0, 10)}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Report content */}
      <div className="flex-1 overflow-auto">
        {!selectedId && (
          <p className="text-gray-600">Select a report from the sidebar.</p>
        )}
        {isLoading && <p className="text-gray-500">Loading report…</p>}
        {report && (
          <div className="prose prose-invert prose-sm max-w-none bg-gray-900 border border-gray-800 rounded-lg p-6">
            <ReactMarkdown>{report.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
