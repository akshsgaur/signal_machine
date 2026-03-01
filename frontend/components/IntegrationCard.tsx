"use client";

import Image from "next/image";
import { useState } from "react";
import { connectIntegration } from "@/lib/api";

interface Props {
  name: string;
  label: string;
  description: string;
  userId: string;
  connected: boolean;
  onConnected: () => void;
  logo?: string;
  connectHref?: string;
  secondaryConnectHref?: string;
  secondaryLabel?: string;
  note?: string;
}

export function IntegrationCard({
  name,
  label,
  description,
  userId,
  connected,
  onConnected,
  logo,
  connectHref,
  secondaryConnectHref,
  secondaryLabel,
  note,
}: Props) {
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleConnect() {
    if (!token.trim()) return;
    setLoading(true);
    setError("");
    try {
      await connectIntegration(userId, name, token.trim());
      setToken("");
      onConnected();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {logo && (
            <Image
              src={logo}
              alt={`${label} logo`}
              width={32}
              height={32}
              className="rounded-md"
            />
          )}
          <div>
            <h3 className="text-white font-semibold text-lg">{label}</h3>
            <p className="text-zinc-400 text-sm mt-0.5">{description}</p>
          </div>
        </div>
        {connected && (
          <span className="flex items-center gap-1.5 text-emerald-400 text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Connected
          </span>
        )}
      </div>

      {!connected && (
        <>
          {connectHref ? (
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={connectHref}
                className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors"
              >
                Connect
              </a>
              {secondaryConnectHref && (
                <a
                  href={secondaryConnectHref}
                  className="px-4 py-2 border border-zinc-700 text-zinc-200 text-sm font-medium rounded-lg hover:border-zinc-500 transition-colors"
                >
                  {secondaryLabel ?? "Enable private access"}
                </a>
              )}
            </div>
          ) : (
            <div className="flex gap-2">
              <input
                type="password"
                placeholder={`Paste ${label} API token`}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500"
                onKeyDown={(e) => e.key === "Enter" && handleConnect()}
              />
              <button
                onClick={handleConnect}
                disabled={loading || !token.trim()}
                className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? "Connecting..." : "Connect"}
              </button>
            </div>
          )}
        </>
      )}

      {error && <p className="text-red-400 text-sm">{error}</p>}
      {note && <p className="text-zinc-500 text-xs">{note}</p>}
    </div>
  );
}
