import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

const STATUS_STYLE = {
  green: "bg-green-500",
  red: "bg-red-500",
  unknown: "bg-gray-500",
};

const SERVICES = [
  { key: "spark", label: "Spark Worker", icon: "⚡" },
  { key: "kafka", label: "Kafka", icon: "📨" },
  { key: "postgres", label: "PostgreSQL", icon: "🗄️" },
  { key: "airflow", label: "Airflow", icon: "🔄" },
];

export default function SystemHealth() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["systemHealth"],
    queryFn: api.getSystemHealth,
    refetchInterval: 10000,
  });

  return (
    <div>
      <h2 className="text-green-400 text-base font-bold mb-4">System Health</h2>

      {isLoading && <p className="text-gray-500">Loading …</p>}
      {error && <p className="text-red-400">Error: {error.message}</p>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {SERVICES.map(({ key, label, icon }) => {
          const status = data?.[key] ?? "unknown";
          return (
            <div
              key={key}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col items-center gap-3"
            >
              <span className="text-2xl">{icon}</span>
              <span className="text-gray-300 text-xs">{label}</span>
              <div className="flex items-center gap-2">
                <span
                  className={`w-3 h-3 rounded-full ${STATUS_STYLE[status] ?? STATUS_STYLE.unknown}`}
                />
                <span
                  className={
                    status === "green"
                      ? "text-green-400"
                      : status === "red"
                      ? "text-red-400"
                      : "text-gray-500"
                  }
                >
                  {status.toUpperCase()}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-6 text-xs text-gray-600">
        Auto-refreshes every 10 seconds · Powered by Prometheus
      </div>
    </div>
  );
}
