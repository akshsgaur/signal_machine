"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { PipelineTracker } from "@/components/PipelineTracker";
import { DecisionBrief } from "@/components/DecisionBrief";
import { useSSE } from "@/lib/useSSE";

export default function RunPage() {
  const params = useParams();
  const runId = typeof params.id === "string" ? params.id : null;

  const { agentStatuses, brief, pipelineStatus } = useSSE(runId);

  const loading = pipelineStatus === "running" && !brief;

  return (
    <main className="min-h-screen px-4 py-10">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-white">Signal Analysis</h1>
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            ← New analysis
          </Link>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6 items-start">
          <PipelineTracker
            agentStatuses={agentStatuses}
            pipelineStatus={pipelineStatus}
          />
          <div className="min-h-[500px]">
            <DecisionBrief brief={brief} loading={loading} />
          </div>
        </div>

        {pipelineStatus === "failed" && (
          <div className="bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm">
            The pipeline encountered an error. Check server logs for details.
          </div>
        )}
      </div>
    </main>
  );
}
