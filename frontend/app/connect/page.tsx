"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { IntegrationCard } from "@/components/IntegrationCard";
import { getIntegrations } from "@/lib/api";

const USER_ID = "demo-user-001";

const INTEGRATIONS = [
  {
    name: "amplitude",
    label: "Amplitude",
    description: "Behavioral analytics — user events, funnels, retention",
  },
  {
    name: "zendesk",
    label: "Zendesk",
    description: "Support tickets — themes, pain points, sentiment",
  },
  {
    name: "productboard",
    label: "Productboard",
    description: "Feature requests — demand signals, user segments",
  },
  {
    name: "linear",
    label: "Linear",
    description: "Engineering backlog — capacity, blockers, velocity",
  },
];

export default function ConnectPage() {
  const [connected, setConnected] = useState<Record<string, boolean>>({});

  async function refreshConnections() {
    try {
      const data = await getIntegrations(USER_ID);
      setConnected(data);
    } catch {
      // ignore — user may not have any tokens yet
    }
  }

  useEffect(() => {
    refreshConnections();
  }, []);

  return (
    <main className="flex flex-col items-center min-h-screen px-4 py-16">
      <div className="w-full max-w-xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Integrations</h1>
            <p className="text-zinc-400 text-sm mt-1">
              Connect your data sources to enable analysis
            </p>
          </div>
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            ← Back
          </Link>
        </div>

        <div className="space-y-4">
          {INTEGRATIONS.map((integration) => (
            <IntegrationCard
              key={integration.name}
              {...integration}
              userId={USER_ID}
              connected={!!connected[integration.name]}
              onConnected={refreshConnections}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
