"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useUser } from "@clerk/nextjs";
import { IntegrationCard } from "@/components/IntegrationCard";
import { getIntegrations, getSlackConnectUrl } from "@/lib/api";

const INTEGRATIONS = [
  {
    name: "amplitude",
    label: "Amplitude",
    description: "Behavioral analytics - user events, funnels, retention",
  },
  {
    name: "zendesk",
    label: "Zendesk",
    description: "Support tickets - themes, pain points, sentiment",
  },
  {
    name: "productboard",
    label: "Productboard",
    description: "Feature requests - demand signals, user segments",
  },
  {
    name: "linear",
    label: "Linear",
    description: "Engineering backlog - capacity, blockers, velocity",
  },
];

export default function ConnectPage() {
  const { user, isLoaded } = useUser();
  const [connected, setConnected] = useState<Record<string, boolean>>({});

  const refreshConnections = useCallback(async () => {
    try {
      if (!user) return;
      const data = await getIntegrations(user.id);
      setConnected(data);
    } catch {
      // ignore - user may not have any tokens yet
    }
  }, [user]);

  useEffect(() => {
    if (isLoaded) refreshConnections();
  }, [isLoaded, refreshConnections]);

  if (!isLoaded) {
    return (
      <main className="flex flex-col items-center min-h-screen px-4 py-16">
        <div className="w-full max-w-xl text-zinc-400 text-sm">Loading...</div>
      </main>
    );
  }

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
            &lt;- Back
          </Link>
        </div>

        <div className="space-y-4">
          <IntegrationCard
            name="slack"
            label="Slack"
            description="Team conversations - channels, DMs, and threads"
            userId={user?.id ?? ""}
            connected={!!connected["slack"]}
            onConnected={refreshConnections}
            connectHref={
              user?.id ? getSlackConnectUrl(user.id, "public") : undefined
            }
            secondaryConnectHref={
              user?.id ? getSlackConnectUrl(user.id, "private") : undefined
            }
            secondaryLabel="Enable private + DMs"
            note="Connects public channels first. Enable private access if you want DMs and private channels."
          />
          {INTEGRATIONS.map((integration) => (
            <IntegrationCard
              key={integration.name}
              {...integration}
              userId={user?.id ?? ""}
              connected={!!connected[integration.name]}
              onConnected={refreshConnections}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
