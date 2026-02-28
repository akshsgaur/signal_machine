"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { startRun } from "@/lib/api";

export function HypothesisForm() {
  const router = useRouter();
  const { user, isLoaded } = useUser();
  const [hypothesis, setHypothesis] = useState("");
  const [productArea, setProductArea] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!hypothesis.trim() || !productArea.trim()) return;
    if (!user) {
      setError("Please sign in to start an analysis.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const runId = await startRun(user.id, hypothesis.trim(), productArea.trim());
      router.push(`/run/${runId}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start analysis");
      setLoading(false);
    }
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full max-w-2xl">
      <h2 className="text-white font-semibold text-2xl mb-1">Validate a hypothesis</h2>
      <p className="text-zinc-400 text-sm mb-6">
        Signal pulls data from your connected tools and synthesizes a decision brief.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-zinc-300 text-sm font-medium mb-1.5">
            Hypothesis
          </label>
          <textarea
            rows={3}
            placeholder="e.g. Users who complete onboarding in under 5 minutes have 2x 30-day retention"
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500 resize-none"
          />
        </div>

        <div>
          <label className="block text-zinc-300 text-sm font-medium mb-1.5">
            Product Area
          </label>
          <input
            type="text"
            placeholder="e.g. Onboarding, Checkout, Settings"
            value={productArea}
            onChange={(e) => setProductArea(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500"
          />
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={
            !isLoaded ||
            loading ||
            !hypothesis.trim() ||
            !productArea.trim()
          }
          className="w-full py-3 bg-white text-black font-semibold rounded-xl hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Starting analysis..." : "Analyze ->"}
        </button>
      </form>
    </div>
  );
}
