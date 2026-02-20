"use client";

import { useEffect, useRef, useState } from "react";
import { getStreamUrl } from "./api";

export type AgentStatus = "pending" | "running" | "complete";
export type PipelineStatus = "running" | "complete" | "failed" | "timeout";

export interface SSEState {
  agentStatuses: Record<string, AgentStatus>;
  brief: string;
  pipelineStatus: PipelineStatus;
}

const AGENTS = ["behavioral", "support", "feature", "execution"];

export function useSSE(runId: string | null): SSEState {
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatus>>(
    Object.fromEntries(AGENTS.map((a) => [a, "pending"]))
  );
  const [brief, setBrief] = useState("");
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus>("running");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    const es = new EventSource(getStreamUrl(runId));
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "agent_update") {
          setAgentStatuses((prev) => ({ ...prev, [msg.agent]: "complete" }));
        } else if (msg.type === "brief_chunk") {
          setBrief(msg.content);
        } else if (msg.type === "status") {
          setPipelineStatus(msg.status);
          es.close();
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [runId]);

  return { agentStatuses, brief, pipelineStatus };
}
