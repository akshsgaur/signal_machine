"use client";

import { useState } from "react";
import {
  connectIntegration,
  startIntegrationOauth,
  type IntegrationProvider,
  type IntegrationStatus,
} from "@/lib/api";

interface Props {
  provider: IntegrationProvider;
  userId: string;
  workspaceId?: string;
  state?: IntegrationStatus;
  onConnected: () => void;
  connectHref?: string;
  secondaryConnectHref?: string;
  secondaryLabel?: string;
  note?: string;
}

function badgeLabel(provider: IntegrationProvider, state?: IntegrationStatus): string {
  if (state?.connected) return "Connected";
  if (provider.status === "blocked") return "Blocked";
  if (provider.auth_mode === "oauth_future") return "Planned";
  if (provider.status === "existing_non_mcp") return "Available";
  if (provider.connectable) return "Available";
  return "Planned";
}

function badgeClasses(label: string): string {
  if (label === "Connected") return "text-emerald-400";
  if (label === "Blocked") return "text-red-400";
  return "text-amber-300";
}

export function IntegrationCard({
  provider,
  userId,
  workspaceId,
  state,
  onConnected,
  connectHref,
  secondaryConnectHref,
  secondaryLabel,
  note,
}: Props) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const connected = !!state?.connected;
  const disabled =
    connected ||
    provider.status !== "supported" ||
    !provider.connectable ||
    provider.auth_mode === "oauth_future";
  const badge = badgeLabel(provider, state);
  const fieldCount = provider.credential_schema.length;

  async function handleConnect() {
    if (!userId) return;
    setLoading(true);
    setError("");
    try {
      if (provider.connection_mode === "oauth_redirect") {
        const payload = await startIntegrationOauth(
          userId,
          provider.id,
          window.location.href
        );
        const consentUrl = payload.consent_url ?? payload.consentUrl;
        if (!consentUrl) {
          throw new Error("Missing Airbyte consent URL.");
        }
        window.location.href = consentUrl;
        return;
      }
      if (provider.connection_mode === "external_link") {
        await connectIntegration(userId, provider.id, {}, { workspaceId });
        onConnected();
        return;
      }
      if (provider.auth_mode === "token" && fieldCount === 1) {
        const field = provider.credential_schema[0];
        await connectIntegration(userId, provider.id, form[field.name] ?? "", { workspaceId });
      } else {
        await connectIntegration(userId, provider.id, form, { workspaceId });
      }
      setForm({});
      onConnected();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  }

  const requiredMissing = provider.credential_schema.some(
    (field) => field.required && !(form[field.name] ?? "").trim()
  );
  const runtimePending = connected && state?.runtime_ready === false;
  const providerNote = state?.note ?? provider.connection_note ?? note;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {provider.logo_path && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={provider.logo_path}
              alt={`${provider.label} logo`}
              className="w-8 h-8 rounded-md object-contain"
            />
          )}
          <div>
            <h3 className="text-white font-semibold text-lg">{provider.label}</h3>
            <p className="text-zinc-400 text-sm mt-0.5">{provider.description}</p>
          </div>
        </div>
        <span className={`flex items-center gap-1.5 text-sm font-medium ${badgeClasses(badge)}`}>
          <span
            className={`w-2 h-2 rounded-full ${
              badge === "Connected"
                ? "bg-emerald-400"
                : badge === "Blocked"
                  ? "bg-red-400"
                  : "bg-amber-300"
            }`}
          />
          {badge}
        </span>
      </div>

      {connectHref && !connected && (
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={connectHref}
            className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors"
          >
            Connect
          </a>
          {provider.connection_mode === "external_link" && (
            <button
              onClick={handleConnect}
              disabled={loading}
              className="px-4 py-2 border border-zinc-700 text-zinc-200 text-sm font-medium rounded-lg hover:border-zinc-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Saving..." : "Mark connected"}
            </button>
          )}
          {secondaryConnectHref && (
            <a
              href={secondaryConnectHref}
              className="px-4 py-2 border border-zinc-700 text-zinc-200 text-sm font-medium rounded-lg hover:border-zinc-500 transition-colors"
            >
              {secondaryLabel ?? "Enable private access"}
            </a>
          )}
        </div>
      )}

      {!connectHref && !disabled && (
        <>
          {provider.auth_mode === "token" && fieldCount === 1 ? (
            <div className="flex gap-2">
              <input
                type="password"
                placeholder={provider.credential_schema[0]?.placeholder ?? `Paste ${provider.label} token`}
                value={form[provider.credential_schema[0]?.name ?? "token"] ?? ""}
                onChange={(e) =>
                  setForm((current) => ({
                    ...current,
                    [provider.credential_schema[0]?.name ?? "token"]: e.target.value,
                  }))
                }
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500"
                onKeyDown={(e) => e.key === "Enter" && !requiredMissing && handleConnect()}
              />
              <button
                onClick={handleConnect}
                disabled={loading || requiredMissing}
                className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "Connecting..." : "Connect"}
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {provider.credential_schema.map((field) => (
                <input
                  key={field.name}
                  type={field.kind === "password" ? "password" : "text"}
                  placeholder={field.placeholder}
                  value={form[field.name] ?? ""}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, [field.name]: e.target.value }))
                  }
                  onKeyDown={(e) => e.key === "Enter" && !requiredMissing && handleConnect()}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500"
                />
              ))}
              <button
                onClick={handleConnect}
                disabled={loading || requiredMissing}
                className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "Saving..." : "Save"}
              </button>
            </div>
          )}
        </>
      )}

      {(provider.reason_unavailable || providerNote) && (
        <p className="text-zinc-500 text-xs">
          {provider.reason_unavailable ?? providerNote}
        </p>
      )}
      {runtimePending && !provider.reason_unavailable && (
        <p className="text-amber-300 text-xs">
          Connected in Airbyte Cloud. Signal chat and pipeline still use the legacy integration runtime.
        </p>
      )}
      {error && <p className="text-red-400 text-sm">{error}</p>}
    </div>
  );
}
