"use client";

import { useEffect, useState } from "react";
import type { AgentStatus, PipelineStatus } from "@/lib/useSSE";

const AGENT_LABELS: Record<string, { label: string; sub: string }> = {
  behavioral: { label: "Behavioral", sub: "Amplitude analytics" },
  support: { label: "Support", sub: "Zendesk tickets" },
  feature: { label: "Feature Demand", sub: "Productboard requests" },
  execution: { label: "Engineering", sub: "Linear backlog" },
  synthesis: { label: "Synthesis", sub: "Decision brief" },
};

interface Props {
  agentStatuses: Record<string, AgentStatus>;
  pipelineStatus: PipelineStatus;
}

function Spinner() {
  return (
    <svg
      className="animate-spin w-4 h-4 text-zinc-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

function Checkmark() {
  return (
    <svg
      className="w-4 h-4 text-emerald-400"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function AgentRow({
  agentKey,
  status,
  elapsed,
}: {
  agentKey: string;
  status: AgentStatus | "complete";
  elapsed: number;
}) {
  const meta = AGENT_LABELS[agentKey];
  const isRunning = status === "running" || (status === "pending" && agentKey !== "synthesis");
  const isDone = status === "complete";

  return (
    <div className="flex items-center gap-3 py-3 border-b border-zinc-800 last:border-0">
      <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
        {isDone ? <Checkmark /> : isRunning ? <Spinner /> : <span className="w-2 h-2 rounded-full bg-zinc-700" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${isDone ? "text-white" : "text-zinc-400"}`}>
          {meta?.label ?? agentKey}
        </p>
        <p className="text-xs text-zinc-500">{meta?.sub}</p>
      </div>
      {isDone && elapsed > 0 && (
        <span className="text-xs text-zinc-500">{elapsed}s</span>
      )}
    </div>
  );
}

export function PipelineTracker({ agentStatuses, pipelineStatus }: Props) {
  const [elapsed, setElapsed] = useState<Record<string, number>>({});
  const [agentStart] = useState<Record<string, number>>({
    behavioral: Date.now(),
    support: Date.now(),
    feature: Date.now(),
    execution: Date.now(),
  });

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      setElapsed((prev) => {
        const next = { ...prev };
        for (const key of ["behavioral", "support", "feature", "execution"]) {
          if (agentStatuses[key] === "complete" && !prev[key]) {
            next[key] = Math.round((now - agentStart[key]) / 1000);
          }
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [agentStatuses, agentStart]);

  const synthesisDone = pipelineStatus === "complete";
  const researchDone = Object.values(agentStatuses).every((s) => s === "complete");

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full">
      <h3 className="text-white font-semibold mb-4">Pipeline</h3>
      <div>
        {["behavioral", "support", "feature", "execution"].map((key) => (
          <AgentRow
            key={key}
            agentKey={key}
            status={agentStatuses[key] ?? "pending"}
            elapsed={elapsed[key] ?? 0}
          />
        ))}
        <AgentRow
          agentKey="synthesis"
          status={synthesisDone ? "complete" : researchDone ? "running" : "pending"}
          elapsed={elapsed["synthesis"] ?? 0}
        />
      </div>
    </div>
  );
}
