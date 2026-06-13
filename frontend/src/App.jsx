import React, { useState } from "react";
import SystemHealth from "./components/SystemHealth";
import IncidentList from "./components/IncidentList";
import AgentActivity from "./components/AgentActivity";
import Reports from "./components/Reports";

const TABS = ["System Health", "Incidents", "Agent Activity", "Reports"];

export default function App() {
  const [tab, setTab] = useState("System Health");
  const [activeIncident, setActiveIncident] = useState(null);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-4">
        <span className="text-green-400 font-bold text-lg tracking-widest">AIOps</span>
        <span className="text-gray-500">|</span>
        <span className="text-gray-400">Data Pipeline Incident Response Platform</span>
      </header>

      {/* Tabs */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6 flex gap-1 pt-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs rounded-t transition-colors ${
              tab === t
                ? "bg-gray-800 text-green-400 border-t border-x border-gray-700"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="flex-1 p-6">
        {tab === "System Health" && <SystemHealth />}
        {tab === "Incidents" && (
          <IncidentList
            activeIncident={activeIncident}
            setActiveIncident={setActiveIncident}
            onViewActivity={() => setTab("Agent Activity")}
          />
        )}
        {tab === "Agent Activity" && (
          <AgentActivity incidentId={activeIncident} />
        )}
        {tab === "Reports" && <Reports />}
      </main>
    </div>
  );
}
