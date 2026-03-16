"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useUser } from "@clerk/nextjs";
import { IntegrationCard } from "@/components/IntegrationCard";
import {
  connectIntegration,
  getIntegrationCatalog,
  getIntegrations,
  getSlackConnectUrl,
  type IntegrationCatalogGroup,
  type IntegrationStatus,
} from "@/lib/api";

const OPENAI_MODELS = [
  { value: "gpt-5.2", label: "GPT-5.2" },
  { value: "gpt-5-nano", label: "GPT-5 Nano" },
  { value: "gpt-5-mini", label: "GPT-5 Mini" },
  { value: "gpt-5.2-pro", label: "GPT-5.2 Pro" },
  { value: "gpt-5", label: "GPT-5" },
];

export default function ConnectPage() {
  const { user, isLoaded } = useUser();
  const [catalog, setCatalog] = useState<IntegrationCatalogGroup[]>([]);
  const [connected, setConnected] = useState<Record<string, IntegrationStatus>>({});
  const [aiModel, setAiModel] = useState("gpt-5.2");
  const [aiKey, setAiKey] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const refreshConnections = useCallback(async () => {
    try {
      if (!user) return;
      const data = await getIntegrations(user.id);
      setConnected(data);
    } catch {
      // ignore - user may not have any integrations yet
    }
  }, [user]);

  const loadCatalog = useCallback(async () => {
    try {
      const data = await getIntegrationCatalog();
      setCatalog(data.groups);
    } catch {
      setCatalog([]);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    if (isLoaded) refreshConnections();
  }, [isLoaded, refreshConnections]);

  async function handleSaveAi() {
    if (!aiKey.trim() || !user) return;
    setAiLoading(true);
    setAiError("");
    try {
      await connectIntegration(user.id, "openai_api_key", aiKey.trim());
      await connectIntegration(user.id, "openai_model", aiModel);
      setAiKey("");
      refreshConnections();
    } catch (err: unknown) {
      setAiError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setAiLoading(false);
    }
  }

  const slackProvider = useMemo(
    () =>
      catalog
        .flatMap((group) => group.providers)
        .find((provider) => provider.id === "slack"),
    [catalog]
  );

  const renderGroups = useMemo(
    () =>
      catalog
        .map((group) => ({
          ...group,
          providers: group.providers.filter((provider) => provider.id !== "slack"),
        }))
        .filter((group) => group.providers.length > 0),
    [catalog]
  );

  if (!isLoaded) {
    return (
      <main className="flex flex-col items-center min-h-screen px-4 py-16">
        <div className="w-full max-w-4xl text-zinc-400 text-sm">Loading...</div>
      </main>
    );
  }

  return (
    <main className="flex flex-col items-center min-h-screen px-4 py-16">
      <div className="w-full max-w-4xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Integrations</h1>
            <p className="text-zinc-400 text-sm mt-1">
              Connect MCP-backed sources for chat and keep the existing analysis pipeline intact.
            </p>
          </div>
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            &lt;- Back
          </Link>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-white font-semibold text-lg">AI Model</h3>
              <p className="text-zinc-400 text-sm mt-0.5">
                OpenAI model that powers the deep analysis pipeline
              </p>
            </div>
            {connected["openai_api_key"]?.connected && (
              <span className="flex items-center gap-1.5 text-emerald-400 text-sm font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                Configured
              </span>
            )}
          </div>

          <div className="flex gap-2">
            <select
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-zinc-500"
            >
              {OPENAI_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            <input
              type="password"
              placeholder="Paste OpenAI API key"
              value={aiKey}
              onChange={(e) => setAiKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSaveAi()}
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500"
            />
            <button
              onClick={handleSaveAi}
              disabled={aiLoading || !aiKey.trim()}
              className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {aiLoading ? "Saving..." : "Save"}
            </button>
          </div>

          {aiError && <p className="text-red-400 text-sm">{aiError}</p>}
        </div>

        {slackProvider && (
          <IntegrationCard
            provider={slackProvider}
            userId={user?.id ?? ""}
            state={connected["slack"]}
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
        )}

        {renderGroups.map((group) => (
          <section key={group.category} className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-white">{group.category}</h2>
              <p className="text-zinc-500 text-sm mt-1">
                {group.category === "Product development" &&
                  "Roadmaps, execution systems, and delivery context."}
                {group.category === "Product analytics and insights" &&
                  "Customer behavior, support signals, and business intelligence."}
                {group.category === "Collaboration" &&
                  "Team communication and shared context."}
                {group.category === "Product design" &&
                  "Design collaboration and prototyping tools."}
                {group.category === "Market intelligence" &&
                  "External analyst and market research sources."}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {group.providers.map((provider) => (
                <IntegrationCard
                  key={provider.id}
                  provider={provider}
                  userId={user?.id ?? ""}
                  state={connected[provider.id]}
                  onConnected={refreshConnections}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
