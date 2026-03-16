"use client";

import Link from "next/link";
import Image from "next/image";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useClerk, useUser, UserButton } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import {
  createInsightsFolder,
  getIntegrations,
  getLinearDashboard,
  getLatestAnalysis,
  getChatTitleStreamUrl,
  getCodeSessionUrl,
  getStreamUrl,
  listChatMessages,
  listChatSessions,
  listCustomerDocs,
  listInsightsFolders,
  startChatSession,
  startRun,
  streamChat,
  uploadCustomerDocs,
  type LinearDashboardResponse,
  type IntegrationStatus,
} from "@/lib/api";

type TabKey = "analysis" | "chat" | "insights" | "builder" | "profile";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "analysis", label: "Dashboard" },
  { key: "chat", label: "Chat" },
  { key: "insights", label: "Insights" },
  { key: "builder", label: "Build With An Coding Agent" },
  { key: "profile", label: "Profile" },
];

const INTEGRATION_LABELS: Record<string, string> = {
  amplitude: "Amplitude",
  zendesk: "Zendesk",
  productboard: "Productboard",
  linear: "Linear",
};

const INTEGRATION_DESCRIPTIONS: Record<string, string> = {
  amplitude: "Behavioral analytics signals",
  zendesk: "Support insights and themes",
  productboard: "Feature demand and requests",
  linear: "Engineering execution reality",
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  status?: "thinking" | "complete" | "error";
  activitySteps?: Array<{
    id: string;
    label: string;
    status: "active" | "complete";
  }>;
  activitySummary?: string;
  showActivityDetails?: boolean;
  isStreaming?: boolean;
};

type ChatSession = {
  id: string;
  title: string | null;
  updated_at?: string | null;
};

type SidebarAction =
  | "scroll-overview"
  | "scroll-connected-tools"
  | "scroll-latest-brief"
  | "scroll-run-status"
  | "new-chat"
  | "open-chat-session"
  | "show-all-files"
  | "show-folder"
  | "new-folder"
  | "open-builder"
  | "open-builder-tab"
  | "open-builder-fullscreen"
  | "manage-integrations"
  | "sign-out";

type SidebarContextItem = {
  key: string;
  label: string;
  action?: SidebarAction;
  payload?: string;
  href?: string;
  badge?: string;
  active?: boolean;
  disabled?: boolean;
};

type SidebarContextGroup = {
  key: string;
  label: string;
  items: SidebarContextItem[];
};

const SIDEBAR_MIN_WIDTH = 248;
const SIDEBAR_MAX_WIDTH = 380;
const SIDEBAR_DEFAULT_WIDTH = 288;
const SIDEBAR_PINNED_STORAGE_KEY = "signal-sidebar-pinned";
const SIDEBAR_WIDTH_STORAGE_KEY = "signal-sidebar-width";

function formatWidgetDate(value?: string) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function DashboardWidgetShell({
  title,
  children,
  className = "",
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl border border-zinc-800 bg-zinc-950 p-5 ${className}`}>
      <div className="text-[11px] uppercase tracking-[0.22em] text-zinc-500">{title}</div>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function WidgetEmpty({ label }: { label: string }) {
  return <div className="text-sm text-zinc-500">{label}</div>;
}

function WidgetError({ label }: { label: string }) {
  return <div className="text-sm text-red-400">{label}</div>;
}

function ThinkingAnimation() {
  return (
    <div className="inline-flex items-center gap-2 px-1 py-1 text-xs text-zinc-500">
      <span className="font-medium tracking-[0.01em]">Thinking</span>
      <span className="thinking-shimmer h-[5px] w-16 rounded-full bg-zinc-800/80" />
    </div>
  );
}

function ChatActivityFeed({
  message,
}: {
  message: ChatMessage;
}) {
  const steps = message.activitySteps ?? [];
  if (!message.isStreaming) {
    return null;
  }

  const showThinking = steps.length === 0;

  return (
    <div className="mb-2 min-h-6">
      {showThinking && <ThinkingAnimation />}
      {!showThinking && (
        <div className="space-y-1">
          {steps.map((step, index) => (
            <div
              key={step.id}
              className={`activity-step flex items-center gap-2 px-1 py-1 text-sm transition-all ${
                step.status === "active" ? "text-zinc-400" : "text-zinc-600"
              }`}
              style={{ animationDelay: `${index * 70}ms` }}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  step.status === "active" ? "bg-zinc-500" : "bg-zinc-700"
                }`}
              />
              <span className={step.status === "active" ? "activity-current" : ""}>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function getRenderedChatTitle(
  session: ChatSession,
  streamingTitles: Record<string, string>
): string {
  return streamingTitles[session.id] || session.title || "Untitled chat";
}

export default function WorkspacePage() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("analysis");
  const [connected, setConnected] = useState<Record<string, IntegrationStatus>>({});
  const [loadingIntegrations, setLoadingIntegrations] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [streamingChatTitles, setStreamingChatTitles] = useState<Record<string, string>>({});
  const [chatLoadingHistory, setChatLoadingHistory] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarPeekOpen, setSidebarPeekOpen] = useState(false);
  const [sidebarHovering, setSidebarHovering] = useState(false);
  const [sidebarTriggerHovering, setSidebarTriggerHovering] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const [sidebarHydrated, setSidebarHydrated] = useState(false);
  const [builderFullscreen, setBuilderFullscreen] = useState(false);
  const [codeSessionUrl, setCodeSessionUrl] = useState("");
  const [codeSessionLoading, setCodeSessionLoading] = useState(true);
  const [codeSessionError, setCodeSessionError] = useState("");
  const [builderIframeLoaded, setBuilderIframeLoaded] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentDone, setAgentDone] = useState<Set<string>>(new Set());
  const [agentRunError, setAgentRunError] = useState("");
  const [insightsUploading, setInsightsUploading] = useState(false);
  const [insightsError, setInsightsError] = useState("");
  const [insightsFolders, setInsightsFolders] = useState<
    Array<{ id: string; name: string; created_at?: string }>
  >([]);
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [newFolderName, setNewFolderName] = useState("");
  const [insightsMenuOpen, setInsightsMenuOpen] = useState(false);
  const [insightsDocs, setInsightsDocs] = useState<
    Array<{
      document_id: string;
      name?: string;
      filename?: string;
      created_at?: string;
      status?: string;
      metadata?: Record<string, string>;
    }>
  >([]);
  const [insightsRefreshing, setInsightsRefreshing] = useState(false);
  const [analysisData, setAnalysisData] = useState<{
    run_id: string | null;
    status: string;
    brief: string | null;
    sources: Record<string, string>;
  } | null>(null);
  const [linearDashboard, setLinearDashboard] = useState<LinearDashboardResponse | null>(null);
  const [linearDashboardLoading, setLinearDashboardLoading] = useState(false);
  const [linearDashboardError, setLinearDashboardError] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Ask me anything about your product. I can summarize trends and signals.",
    },
  ]);
  const folderUploadRef = useRef<HTMLInputElement | null>(null);
  const autoRunAttemptedRef = useRef(false);
  const activeTitleStreamsRef = useRef<Map<string, EventSource>>(new Map());
  const sidebarResizeStartRef = useRef({ x: 0, width: SIDEBAR_DEFAULT_WIDTH });
  const overviewRef = useRef<HTMLDivElement | null>(null);
  const connectedToolsRef = useRef<HTMLDivElement | null>(null);
  const latestBriefRef = useRef<HTMLDivElement | null>(null);
  const runStatusRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isLoaded && !user) {
      router.replace("/auth/sign-in?allow=1");
    }
  }, [isLoaded, router, user]);

  useEffect(() => {
    try {
      const storedPinned = window.localStorage.getItem(SIDEBAR_PINNED_STORAGE_KEY);
      const storedWidth = window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY);
      if (storedPinned === "true" || storedPinned === "false") {
        setSidebarOpen(storedPinned === "true");
      }
      if (storedWidth) {
        const parsedWidth = Number(storedWidth);
        if (!Number.isNaN(parsedWidth)) {
          setSidebarWidth(
            Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, parsedWidth))
          );
        }
      }
    } finally {
      setSidebarHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (sidebarOpen) return;
    if (!sidebarHovering && !sidebarTriggerHovering && sidebarPeekOpen) {
      setSidebarPeekOpen(false);
    }
  }, [sidebarHovering, sidebarOpen, sidebarPeekOpen, sidebarTriggerHovering]);

  useEffect(() => {
    if (!sidebarHydrated) return;
    window.localStorage.setItem(SIDEBAR_PINNED_STORAGE_KEY, String(sidebarOpen));
  }, [sidebarHydrated, sidebarOpen]);

  useEffect(() => {
    if (!sidebarHydrated) return;
    window.localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, String(sidebarWidth));
  }, [sidebarHydrated, sidebarWidth]);

  useEffect(() => {
    if (!isResizingSidebar) return;

    function handlePointerMove(event: MouseEvent) {
      const delta = event.clientX - sidebarResizeStartRef.current.x;
      const nextWidth = Math.min(
        SIDEBAR_MAX_WIDTH,
        Math.max(SIDEBAR_MIN_WIDTH, sidebarResizeStartRef.current.width + delta)
      );
      setSidebarWidth(nextWidth);
    }

    function handlePointerUp() {
      setIsResizingSidebar(false);
    }

    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp);
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";

    return () => {
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [isResizingSidebar]);

  useEffect(() => {
    let mounted = true;
    async function loadIntegrations() {
      try {
        if (!user) return;
        const data = await getIntegrations(user.id);
        if (mounted) setConnected(data);
      } catch {
        if (mounted) setConnected({});
      } finally {
        if (mounted) setLoadingIntegrations(false);
      }
    }
    if (isLoaded) loadIntegrations();
    return () => {
      mounted = false;
    };
  }, [isLoaded, user]);

  useEffect(() => {
    let mounted = true;
    async function loadCodeSession() {
      try {
        if (!user?.id) return;
        setCodeSessionLoading(true);
        setCodeSessionError("");
        const data = await getCodeSessionUrl(user.id);
        if (mounted) {
          setCodeSessionUrl(data.url);
          setBuilderIframeLoaded(false);
        }
      } catch (err) {
        console.error("Failed to fetch code session URL", err);
        if (mounted) {
          setCodeSessionUrl("");
          setCodeSessionError(
            err instanceof Error ? err.message : "Failed to boot the coding workspace."
          );
        }
      } finally {
        if (mounted) setCodeSessionLoading(false);
      }
    }
    if (isLoaded && user?.id) loadCodeSession();
    return () => {
      mounted = false;
    };
  }, [isLoaded, user]);

  useEffect(() => {
    return () => {
      activeTitleStreamsRef.current.forEach((source) => source.close());
      activeTitleStreamsRef.current.clear();
    };
  }, []);

  const refreshChatSessions = useCallback(async () => {
    if (!user) return;
    try {
      const sessions = await listChatSessions(user.id);
      setChatSessions(sessions);
    } catch {
      setChatSessions([]);
    }
  }, [user]);

  useEffect(() => {
    refreshChatSessions();
  }, [refreshChatSessions]);

  const refreshAnalysis = useCallback(async () => {
    if (!user) return;
    setAnalysisLoading(true);
    setAnalysisError("");
    try {
      const data = await getLatestAnalysis(user.id);
      setAnalysisData(data);
    } catch (err: unknown) {
      setAnalysisData(null);
      setAnalysisError(err instanceof Error ? err.message : "Failed to load analysis");
    } finally {
      setAnalysisLoading(false);
    }
  }, [user]);

  const refreshLinearDashboard = useCallback(async () => {
    if (!user) return;
    if (!connected.linear?.connected) {
      setLinearDashboard(null);
      setLinearDashboardError("");
      setLinearDashboardLoading(false);
      return;
    }
    setLinearDashboardLoading(true);
    setLinearDashboardError("");
    try {
      const data = await getLinearDashboard(user.id);
      setLinearDashboard(data);
    } catch (err: unknown) {
      setLinearDashboard(null);
      setLinearDashboardError(
        err instanceof Error ? err.message : "Failed to load Linear widgets"
      );
    } finally {
      setLinearDashboardLoading(false);
    }
  }, [connected.linear?.connected, user]);

  const refreshDashboardData = useCallback(async () => {
    await Promise.all([refreshAnalysis(), refreshLinearDashboard()]);
  }, [refreshAnalysis, refreshLinearDashboard]);

  const runDeepAgent = useCallback(async () => {
    if (!user || agentRunning) return;
    setAgentRunning(true);
    setAgentDone(new Set());
    setAgentRunError("");
    try {
      const runId = await startRun(
        user.id,
        "Analyze all product signals and customer feedback to surface key trends, risks, and opportunities",
        "All"
      );
      const es = new EventSource(getStreamUrl(runId));
      es.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "agent_update" && msg.status === "complete") {
            setAgentDone((prev) => new Set(Array.from(prev).concat(msg.agent)));
          }
          if (msg.type === "status" && (msg.status === "complete" || msg.status === "failed" || msg.status === "timeout")) {
            es.close();
            setAgentRunning(false);
            if (msg.status === "complete") {
              refreshAnalysis();
            } else {
              setAgentRunError("Run ended with status: " + msg.status);
            }
          }
        } catch {}
      };
      es.onerror = () => {
        es.close();
        setAgentRunning(false);
        setAgentRunError("Connection lost. Try again.");
      };
    } catch (err: unknown) {
      setAgentRunning(false);
      setAgentRunError(err instanceof Error ? err.message : "Failed to start run");
    }
  }, [user, agentRunning, refreshAnalysis]);

  const connectedIntegrations = useMemo(
    () =>
      Object.keys(connected).filter(
        (key) => connected[key]?.connected && connected[key]?.pipeline_enabled
      ),
    [connected]
  );
  const hasSourceAnalysis = useMemo(
    () => !!analysisData && Object.keys(analysisData.sources ?? {}).length > 0,
    [analysisData]
  );
  const linearWidgets = linearDashboard?.widgets;
  const showLinearWidgets = !!connected.linear?.connected && !!linearWidgets;
  const showLinearWidgetNotice =
    !!connected.linear?.connected &&
    !linearDashboardLoading &&
    !showLinearWidgets &&
    !linearDashboardError;

  useEffect(() => {
    refreshAnalysis();
  }, [refreshAnalysis]);

  useEffect(() => {
    if (loadingIntegrations) return;
    if (!connected.linear?.connected) {
      setLinearDashboard(null);
      setLinearDashboardError("");
      setLinearDashboardLoading(false);
      return;
    }
    refreshLinearDashboard();
  }, [connected.linear?.connected, loadingIntegrations, refreshLinearDashboard]);

  useEffect(() => {
    if (!user || loadingIntegrations) return;

    if (connectedIntegrations.length === 0) {
      autoRunAttemptedRef.current = false;
      return;
    }

    const hasExistingAnalysis =
      !!analysisData && analysisData.status !== "none" && !!analysisData.run_id;

    if (hasExistingAnalysis) {
      autoRunAttemptedRef.current = true;
      return;
    }

    if (analysisLoading || agentRunning || autoRunAttemptedRef.current) {
      return;
    }

    autoRunAttemptedRef.current = true;
    runDeepAgent();
  }, [
    user,
    loadingIntegrations,
    connectedIntegrations.length,
    analysisData,
    analysisLoading,
    agentRunning,
    runDeepAgent,
  ]);


  const refreshInsights = useCallback(async () => {
    if (!user) return;
    setInsightsRefreshing(true);
    try {
      const data = await listCustomerDocs(user.id, activeFolder ?? undefined);
      setInsightsDocs(data.documents || []);
    } catch {
      setInsightsDocs([]);
    } finally {
      setInsightsRefreshing(false);
    }
  }, [user, activeFolder]);

  useEffect(() => {
    refreshInsights();
  }, [refreshInsights]);

  useEffect(() => {
    async function loadFolders() {
      if (!user) return;
      try {
        const data = await listInsightsFolders(user.id);
        setInsightsFolders(data);
      } catch {
        setInsightsFolders([]);
      }
    }
    loadFolders();
  }, [user]);

  useEffect(() => {
    if (!insightsDocs.some((doc) => (doc.status ?? "").toLowerCase() === "processing")) {
      return;
    }
    const timer = setInterval(() => {
      refreshInsights();
    }, 5000);
    return () => clearInterval(timer);
  }, [insightsDocs, refreshInsights]);

  useEffect(() => {
    if (folderUploadRef.current) {
      folderUploadRef.current.setAttribute("webkitdirectory", "true");
      folderUploadRef.current.setAttribute("directory", "true");
    }
  }, []);

  const startTitleStream = useCallback(
    (sessionId: string) => {
      const existing = activeTitleStreamsRef.current.get(sessionId);
      if (existing) {
        existing.close();
      }

      const es = new EventSource(getChatTitleStreamUrl(sessionId));
      activeTitleStreamsRef.current.set(sessionId, es);

      es.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as
            | { type: "title_start"; session_id: string }
            | { type: "title_delta"; session_id: string; content: string }
            | { type: "title_complete"; session_id: string; title: string }
            | { type: "title_error"; session_id: string };

          if (message.type === "title_delta") {
            setStreamingChatTitles((current) => ({
              ...current,
              [sessionId]: message.content,
            }));
            return;
          }

          if (message.type === "title_complete") {
            setStreamingChatTitles((current) => ({
              ...current,
              [sessionId]: message.title,
            }));
            es.close();
            activeTitleStreamsRef.current.delete(sessionId);
            void refreshChatSessions();
            return;
          }

          if (message.type === "title_error") {
            es.close();
            activeTitleStreamsRef.current.delete(sessionId);
          }
        } catch {
          es.close();
          activeTitleStreamsRef.current.delete(sessionId);
        }
      };

      es.onerror = () => {
        es.close();
        activeTitleStreamsRef.current.delete(sessionId);
      };
    },
    [refreshChatSessions]
  );

  const updateAssistantPlaceholder = useCallback(
    (
      messageId: string,
      update: (message: ChatMessage) => ChatMessage
    ) => {
      setChatMessages((prev) =>
        prev.map((message) =>
          message.id === messageId ? update(message) : message
        )
      );
    },
    []
  );

  async function sendMessage() {
    const content = chatInput.trim();
    if (!content) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content,
    };
    const assistantPlaceholderId = `a-pending-${Date.now()}`;
    const assistantPlaceholder: ChatMessage = {
      id: assistantPlaceholderId,
      role: "assistant",
      content: "",
      status: "thinking",
      activitySteps: [],
      activitySummary: "Thinking",
      showActivityDetails: false,
      isStreaming: true,
      sources: [],
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatMessages((prev) => [...prev, assistantPlaceholder]);
    setChatInput("");
    setChatSending(true);
    setChatError("");

    try {
      if (!user) {
        throw new Error("Please sign in to chat.");
      }
      let activeSessionId = chatSessionId;
      if (!activeSessionId) {
        const session = await startChatSession(user.id, content, "Product chat");
        const newSessionId = session.session_id;
        activeSessionId = newSessionId;
        setChatSessionId(newSessionId);
        setChatSessions((prev) => [
          {
            id: newSessionId,
            title: session.title,
            updated_at: new Date().toISOString(),
          },
          ...prev.filter((existing) => existing.id !== newSessionId),
        ]);
        setStreamingChatTitles((current) => ({
          ...current,
          [newSessionId]: session.title,
        }));
        startTitleStream(newSessionId);
      }
      const payload = chatMessages
        .filter((msg) => msg.role === "user" || msg.role === "assistant")
        .map((msg) => ({ role: msg.role, content: msg.content }))
        .concat({ role: "user", content });

      await streamChat(
        user.id,
        payload,
        activeSessionId ?? undefined,
        undefined,
        activeFolder ?? undefined,
        {
          onEvent: (event) => {
            if (event.type === "thinking_start") {
              updateAssistantPlaceholder(assistantPlaceholderId, (message) => ({
                ...message,
                status: "thinking",
                activitySummary: "Thinking",
                isStreaming: true,
              }));
              return;
            }

            if (event.type === "activity_step") {
              updateAssistantPlaceholder(assistantPlaceholderId, (message) => {
                const existing = message.activitySteps ?? [];
                const nextStatus: "active" | "complete" = event.status;
                const nextSteps: Array<{
                  id: string;
                  label: string;
                  status: "active" | "complete";
                }> = existing.some((step) => step.id === event.step_id)
                  ? existing.map((step) =>
                      step.id === event.step_id
                        ? { id: step.id, label: event.label, status: nextStatus }
                        : event.status === "active"
                          ? { id: step.id, label: step.label, status: "complete" as const }
                          : { id: step.id, label: step.label, status: step.status }
                    )
                  : [
                      ...existing.map((step) =>
                        event.status === "active"
                          ? { id: step.id, label: step.label, status: "complete" as const }
                          : { id: step.id, label: step.label, status: step.status }
                      ),
                      { id: event.step_id, label: event.label, status: nextStatus },
                    ];

                return {
                  ...message,
                  status: "thinking",
                  activitySummary: undefined,
                  activitySteps: nextSteps,
                  isStreaming: true,
                };
              });
              return;
            }

            if (event.type === "activity_complete") {
              updateAssistantPlaceholder(assistantPlaceholderId, (message) => ({
                ...message,
                activitySummary: undefined,
                showActivityDetails: false,
              }));
              return;
            }

            if (event.type === "final_response") {
              updateAssistantPlaceholder(assistantPlaceholderId, (message) => ({
                ...message,
                content: event.message,
                sources: event.sources_used,
                status: "complete",
              }));
              setChatSessionId(event.session_id);
              return;
            }

            if (event.type === "done") {
              updateAssistantPlaceholder(assistantPlaceholderId, (message) => ({
                ...message,
                isStreaming: false,
                status: message.status === "error" ? "error" : "complete",
                activitySummary: undefined,
                activitySteps: [],
                showActivityDetails: false,
              }));
              void refreshChatSessions();
              return;
            }

            if (event.type === "error") {
              updateAssistantPlaceholder(assistantPlaceholderId, (message) => ({
                ...message,
                status: "error",
                isStreaming: false,
                content: message.content || "The chat request failed. Please try again.",
                activitySummary: undefined,
                activitySteps: [],
              }));
              setChatError(event.message);
            }
          },
        }
      );
    } catch (err: unknown) {
      setChatMessages((prev) =>
        prev.map((message) =>
          message.id === assistantPlaceholderId
            ? {
                ...message,
                status: "error",
                isStreaming: false,
                content: "The chat request failed. Please try again.",
                activitySummary: undefined,
                activitySteps: [],
              }
            : message
        )
      );
      setChatError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setChatSending(false);
    }
  }

  async function loadSession(sessionId: string) {
    if (!user) return;
    setChatLoadingHistory(true);
    setChatError("");
    try {
      const messages = await listChatMessages(sessionId);
      setChatMessages(
        messages.map((msg) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          sources: msg.sources_used,
        }))
      );
      setChatSessionId(sessionId);
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setChatLoadingHistory(false);
    }
  }

  function startNewChat() {
    setChatSessionId(null);
    setChatMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "Ask me anything about your product. I can summarize trends and signals.",
      },
    ]);
  }



  async function handleInsightsUpload(files: FileList | null) {
    if (!files || !user) return;
    setInsightsUploading(true);
    setInsightsError("");
    try {
      const payload = Array.from(files);
      await uploadCustomerDocs(user.id, payload, activeFolder ?? undefined);
      const data = await listCustomerDocs(user.id, activeFolder ?? undefined);
      setInsightsDocs(data.documents || []);
    } catch (err: unknown) {
      setInsightsError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setInsightsUploading(false);
    }
  }

  async function handleCreateFolder(name?: string) {
    const folderName = (name ?? newFolderName).trim();
    if (!user || !folderName) return;
    setInsightsError("");
    try {
      const created = await createInsightsFolder(user.id, folderName);
      setInsightsFolders((prev) => [...prev, created]);
      setActiveFolder(created.name);
      setNewFolderName("");
    } catch (err: unknown) {
      setInsightsError(err instanceof Error ? err.message : "Failed to create folder");
    }
  }

  function handleMenuCreateFolder() {
    setInsightsMenuOpen(false);
    const name = prompt("New folder name");
    if (!name) return;
    handleCreateFolder(name);
  }

  function scrollToSection(ref: RefObject<HTMLDivElement | null>) {
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleSidebarAction(action?: SidebarAction, payload?: string) {
    if (!action) return;
    switch (action) {
      case "scroll-overview":
        scrollToSection(overviewRef);
        break;
      case "scroll-connected-tools":
        scrollToSection(connectedToolsRef);
        break;
      case "scroll-latest-brief":
        if (latestBriefRef.current) {
          scrollToSection(latestBriefRef);
        } else {
          scrollToSection(connectedToolsRef);
        }
        break;
      case "scroll-run-status":
        scrollToSection(runStatusRef);
        break;
      case "new-chat":
        startNewChat();
        setActiveTab("chat");
        break;
      case "open-chat-session":
        if (payload) {
          setActiveTab("chat");
          await loadSession(payload);
        }
        break;
      case "show-all-files":
        setActiveFolder(null);
        setActiveTab("insights");
        break;
      case "show-folder":
        if (payload) {
          setActiveFolder(payload);
          setActiveTab("insights");
        }
        break;
      case "new-folder":
        setActiveTab("insights");
        handleMenuCreateFolder();
        break;
      case "open-builder":
        if (codeSessionUrl) {
          window.open(codeSessionUrl, "_blank", "noopener,noreferrer");
        }
        break;
      case "open-builder-tab":
        setActiveTab("builder");
        break;
      case "open-builder-fullscreen":
        if (codeSessionUrl) {
          setActiveTab("builder");
          setBuilderFullscreen(true);
        }
        break;
      case "manage-integrations":
        router.push("/connect");
        break;
      case "sign-out":
        await signOut({ redirectUrl: "/" });
        break;
      default:
        break;
    }
  }

  const isSidebarPinned = sidebarOpen;
  const isSidebarPeeking = !sidebarOpen && sidebarPeekOpen;
  const isSidebarVisible = isSidebarPinned || isSidebarPeeking;
  const contentInset = isSidebarPinned ? sidebarWidth + 16 : 0;
  const workspaceName = user?.firstName ? `${user.firstName}'s Workspace` : "Workspace";

  const sidebarContextGroups = useMemo<SidebarContextGroup[]>(() => {
    if (activeTab === "analysis") {
      return [];
    }

    if (activeTab === "chat") {
      return [
        {
          key: "chat-actions",
          label: "Chat",
          items: [
            { key: "new-chat", label: "New chat", action: "new-chat" },
            ...chatSessions.map((session) => ({
              key: session.id,
              label: getRenderedChatTitle(session, streamingChatTitles),
              action: "open-chat-session" as SidebarAction,
              payload: session.id,
              active: session.id === chatSessionId,
            })),
          ],
        },
      ];
    }

    if (activeTab === "insights") {
      return [
        {
          key: "insights-folders",
          label: "Insights",
          items: [
            {
              key: "all-files",
              label: "All files",
              action: "show-all-files",
              active: !activeFolder,
            },
            ...insightsFolders.map((folder) => ({
              key: folder.id,
              label: folder.name,
              action: "show-folder" as SidebarAction,
              payload: folder.name,
              active: activeFolder === folder.name,
            })),
            { key: "new-folder", label: "New folder", action: "new-folder" },
          ],
        },
      ];
    }

    if (activeTab === "builder") {
      return [
        {
          key: "builder-actions",
          label: "Builder",
          items: [
            { key: "ide", label: "IDE", action: "open-builder-tab", active: true },
            {
              key: "open-new-tab",
              label: "Open in new tab",
              action: "open-builder",
              disabled: !codeSessionUrl,
            },
            {
              key: "fullscreen",
              label: "Fullscreen",
              action: "open-builder-fullscreen",
              disabled: !codeSessionUrl,
            },
          ],
          chips: [
            {
              key: "builder-status",
              label: codeSessionLoading
                ? "Booting"
                : codeSessionError
                  ? "Error"
                  : codeSessionUrl
                    ? "Ready"
                    : "Unavailable",
              tone:
                codeSessionLoading || codeSessionUrl
                  ? "accent"
                  : "default",
            },
          ],
        },
      ];
    }

    if (activeTab === "profile") {
      return [
        {
          key: "profile-actions",
          label: "Profile",
          items: [
            { key: "account", label: "Account", active: true },
            {
              key: "manage-integrations",
              label: "Manage integrations",
              action: "manage-integrations",
            },
            { key: "sign-out", label: "Sign out", action: "sign-out" },
          ],
        },
      ];
    }

    return [];
  }, [
    activeFolder,
    activeTab,
    chatSessionId,
    chatSessions,
    codeSessionError,
    codeSessionLoading,
    codeSessionUrl,
    insightsFolders,
  ]);

  if (!isLoaded) {
    return (
      <main className="min-h-screen bg-[#0A0A0A] text-white flex items-center justify-center">
        <div className="text-sm text-zinc-400">Loading...</div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-black text-white">
      {(!isLoaded || !user) && (
        <div className="min-h-screen flex items-center justify-center px-6 text-center">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 p-6 text-sm text-zinc-300">
            Redirecting to sign in...
          </div>
        </div>
      )}
      {isLoaded && user && (
      <div className="w-full bg-black px-4 py-5">
        <div
          className="mx-auto w-full max-w-[1440px] transition-[padding-left] duration-300 ease-out"
          style={{ paddingLeft: contentInset }}
        >
        <div className="mb-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                if (isSidebarPeeking) {
                  setSidebarOpen(true);
                  setSidebarPeekOpen(false);
                  return;
                }
                setSidebarOpen((current) => !current);
                setSidebarPeekOpen(false);
              }}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-800 bg-black text-zinc-300 hover:border-zinc-700 hover:text-white"
              aria-label={sidebarOpen ? "Close menu" : "Open menu"}
            >
              {"≡"}
            </button>
            <div>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">
                {workspaceName}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/connect"
              className="rounded-xl border border-zinc-800 bg-black px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
            >
              Manage integrations
            </Link>
            {user && (
              <button
                onClick={() => signOut({ redirectUrl: "/" })}
                className="text-xs uppercase tracking-[0.2em] text-zinc-400 hover:text-white"
              >
                Log out
              </button>
            )}
            <UserButton />
          </div>
        </div>

        <div className="relative min-h-[calc(100vh-120px)]">
          <div
            className="fixed left-0 top-0 bottom-0 z-20 w-6"
            onMouseEnter={() => {
              setSidebarTriggerHovering(true);
              if (!sidebarOpen) setSidebarPeekOpen(true);
            }}
            onMouseLeave={() => {
              setSidebarTriggerHovering(false);
            }}
          />
          <aside
            onMouseEnter={() => {
              setSidebarHovering(true);
              if (!sidebarOpen) setSidebarPeekOpen(true);
            }}
            onMouseLeave={() => {
              setSidebarHovering(false);
              if (!sidebarOpen) setSidebarPeekOpen(false);
            }}
            className={`fixed left-4 top-[92px] bottom-6 z-30 overflow-hidden rounded-[24px] border border-zinc-800 bg-zinc-950/95 shadow-[0_18px_50px_rgba(0,0,0,0.35)] transition-transform duration-300 ease-out ${
              isSidebarPeeking ? "backdrop-blur-sm" : ""
            }`}
            style={{
              width: sidebarWidth,
              transform: isSidebarVisible
                ? "translateX(0)"
                : "translateX(calc(-100% - 24px))",
            }}
          >
            <div className="flex h-full flex-col">
              <div className="border-b border-zinc-800 px-4 py-4">
                <div className="truncate text-base font-semibold text-white">
                  {workspaceName}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-3 py-4">
                <div className="px-3 text-[11px] uppercase tracking-[0.22em] text-zinc-600">
                  Sections
                </div>
                <div className="mt-2 space-y-1">
                  {TABS.map((tab) => {
                    const isActive = tab.key === activeTab;
                    return (
                      <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left text-[15px] transition-colors ${
                          isActive
                            ? "bg-zinc-900 text-white"
                            : "text-zinc-400 hover:bg-zinc-900 hover:text-white"
                        }`}
                      >
                        <span>{tab.label}</span>
                        <span className="text-xs text-zinc-600">{isActive ? "•" : ">"}</span>
                      </button>
                    );
                  })}
                </div>

                <div className="mt-6 space-y-4">
                  {sidebarContextGroups.map((group) => (
                    <div key={group.key}>
                      <div className="px-3 text-[11px] uppercase tracking-[0.22em] text-zinc-600">
                        {group.label}
                      </div>
                      <div className="mt-2 space-y-1">
                        {group.items.map((item) => {
                          const itemClasses = item.active
                            ? "bg-zinc-900 text-white"
                            : "text-zinc-400 hover:bg-zinc-900 hover:text-white";
                          if (item.href && !item.disabled) {
                            return (
                              <a
                                key={item.key}
                                href={item.href}
                                className={`flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left text-[15px] transition-colors ${itemClasses}`}
                              >
                                <span className="truncate">{item.label}</span>
                                {item.badge && (
                                  <span className="ml-3 text-xs text-zinc-500">
                                    {item.badge}
                                  </span>
                                )}
                              </a>
                            );
                          }
                          return (
                            <button
                              key={item.key}
                              type="button"
                              disabled={item.disabled}
                              onClick={() => handleSidebarAction(item.action, item.payload)}
                              className={`flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left text-[15px] transition-colors ${
                                item.disabled
                                  ? "cursor-not-allowed text-zinc-700"
                                  : itemClasses
                              }`}
                            >
                              <span className="truncate">{item.label}</span>
                              {item.badge && (
                                <span className="ml-3 text-xs text-zinc-500">
                                  {item.badge}
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onMouseDown={(event) => {
                  if (!isSidebarPinned) return;
                  sidebarResizeStartRef.current = {
                    x: event.clientX,
                    width: sidebarWidth,
                  };
                  setIsResizingSidebar(true);
                }}
                className={`absolute right-0 top-0 h-full w-3 cursor-ew-resize transition-opacity ${
                  isSidebarPinned ? "opacity-100" : "opacity-0"
                }`}
                aria-label="Resize sidebar"
              >
                <span className="absolute inset-y-0 right-1 flex items-center">
                  <span className="h-12 w-[3px] rounded-full bg-zinc-700/80" />
                </span>
              </button>
            </div>
          </aside>

          <section className="space-y-6">
            {activeTab === "analysis" && (
              <div className="space-y-6">
                <div ref={overviewRef} className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-white">Dashboard</h2>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={runDeepAgent}
                      disabled={agentRunning}
                      className="rounded-xl border border-zinc-800 bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {agentRunning ? "Running..." : "Run analysis again"}
                    </button>
                    <button
                      onClick={refreshDashboardData}
                      disabled={analysisLoading || linearDashboardLoading}
                      className="rounded-xl border border-zinc-800 bg-black px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
                    >
                      {analysisLoading || linearDashboardLoading ? "Refreshing..." : "Refresh"}
                    </button>
                  </div>
                </div>

                {agentRunning && (
                  <div
                    ref={runStatusRef}
                    className="flex flex-wrap gap-3 rounded-2xl border border-zinc-800 bg-black p-4"
                  >
                    {[
                      { key: "behavioral", label: "Amplitude", integration: "amplitude" },
                      { key: "support", label: "Zendesk", integration: "zendesk" },
                      { key: "feature", label: "Productboard", integration: "productboard" },
                      { key: "execution", label: "Linear", integration: "linear" },
                      { key: "insights", label: "Customer Insights", integration: null },
                    ].filter(({ integration }) => integration === null || connected[integration]?.connected)
                    .map(({ key, label }) => (
                      <span
                        key={key}
                        className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border ${
                          agentDone.has(key)
                            ? "border-emerald-500/50 text-emerald-400 bg-emerald-500/10"
                            : "border-zinc-700 text-zinc-500 bg-zinc-800/50"
                        }`}
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${agentDone.has(key) ? "bg-emerald-400" : "bg-zinc-600 animate-pulse"}`} />
                        {label}
                      </span>
                    ))}
                  </div>
                )}

                {agentRunError && (
                  <div className="mb-3 text-sm text-red-400">{agentRunError}</div>
                )}

                {analysisError && (
                  <div className="mb-3 text-sm text-red-400">{analysisError}</div>
                )}

                {connected.linear?.connected && linearDashboardError && !showLinearWidgets && (
                  <div className="rounded-2xl border border-zinc-800 bg-black p-4 text-sm text-red-400">
                    {linearDashboardError}
                  </div>
                )}

                {showLinearWidgetNotice && (
                  <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
                    <div className="text-sm font-medium text-amber-300">
                      Linear widgets are connected but did not load.
                    </div>
                    <div className="mt-1 text-sm text-zinc-400">
                      The dashboard fell back to the stored brief because the live Linear
                      widget payload was empty. Try refreshing. If this persists, the
                      deployed backend may not have the new dashboard route live yet.
                    </div>
                  </div>
                )}

                {!agentRunning && <div ref={runStatusRef} />}

                {connected.linear?.connected && linearDashboardLoading && !showLinearWidgets && (
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <div
                        key={index}
                        className={`rounded-2xl border border-zinc-800 bg-zinc-950 p-5 ${
                          index === 3 ? "lg:col-span-2" : ""
                        }`}
                      >
                        <div className="h-3 w-28 animate-pulse rounded bg-zinc-800" />
                        <div className="mt-4 space-y-3">
                          <div className="h-4 w-full animate-pulse rounded bg-zinc-900" />
                          <div className="h-4 w-5/6 animate-pulse rounded bg-zinc-900" />
                          <div className="h-4 w-2/3 animate-pulse rounded bg-zinc-900" />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {showLinearWidgets && (
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                    <DashboardWidgetShell title="Cycle Progress">
                      {linearWidgets?.cycle_progress.error ? (
                        <WidgetError label={linearWidgets.cycle_progress.error} />
                      ) : (
                        <div className="space-y-4">
                          <div>
                            <div className="text-lg font-semibold text-white">
                              {linearWidgets?.cycle_progress.active_cycle?.name ?? "No active cycle"}
                            </div>
                            {linearWidgets?.cycle_progress.active_cycle && (
                              <div className="mt-1 text-sm text-zinc-500">
                                {formatWidgetDate(
                                  linearWidgets.cycle_progress.active_cycle.starts_at
                                )}
                                {linearWidgets.cycle_progress.active_cycle.ends_at
                                  ? ` - ${formatWidgetDate(
                                      linearWidgets.cycle_progress.active_cycle.ends_at
                                    )}`
                                  : ""}
                              </div>
                            )}
                          </div>
                          <div>
                            <div className="flex items-end justify-between">
                              <div className="text-3xl font-semibold text-white">
                                {linearWidgets?.cycle_progress.completion_pct ?? "--"}%
                              </div>
                              <div className="text-xs uppercase tracking-[0.18em] text-zinc-500">
                                completion
                              </div>
                            </div>
                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-900">
                              <div
                                className="h-full rounded-full bg-emerald-500"
                                style={{
                                  width: `${
                                    linearWidgets?.cycle_progress.completion_pct ?? 0
                                  }%`,
                                }}
                              />
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-3 text-sm">
                            <div className="rounded-xl border border-zinc-800 p-3">
                              <div className="text-zinc-500">Done</div>
                              <div className="mt-1 font-semibold text-white">
                                {linearWidgets?.cycle_progress.counts?.done ?? 0}
                              </div>
                            </div>
                            <div className="rounded-xl border border-zinc-800 p-3">
                              <div className="text-zinc-500">Active</div>
                              <div className="mt-1 font-semibold text-white">
                                {linearWidgets?.cycle_progress.counts?.active ?? 0}
                              </div>
                            </div>
                            <div className="rounded-xl border border-zinc-800 p-3">
                              <div className="text-zinc-500">Total</div>
                              <div className="mt-1 font-semibold text-white">
                                {linearWidgets?.cycle_progress.counts?.total ?? 0}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </DashboardWidgetShell>

                    <DashboardWidgetShell title="Issue Status Breakdown">
                      {linearWidgets?.issue_status_breakdown.error ? (
                        <WidgetError label={linearWidgets.issue_status_breakdown.error} />
                      ) : (
                        <div className="grid grid-cols-2 gap-3">
                          {[
                            ["Backlog", linearWidgets?.issue_status_breakdown.counts?.backlog ?? 0],
                            ["Active", linearWidgets?.issue_status_breakdown.counts?.active ?? 0],
                            ["Blocked", linearWidgets?.issue_status_breakdown.counts?.blocked ?? 0],
                            ["Done", linearWidgets?.issue_status_breakdown.counts?.done ?? 0],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-xl border border-zinc-800 p-4">
                              <div className="text-sm text-zinc-500">{label}</div>
                              <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </DashboardWidgetShell>

                    <DashboardWidgetShell title="Team Load">
                      {linearWidgets?.team_load.error ? (
                        <WidgetError label={linearWidgets.team_load.error} />
                      ) : linearWidgets?.team_load.items?.length ? (
                        <div className="space-y-3">
                          {linearWidgets.team_load.items.map((item) => (
                            <div
                              key={item.id ?? item.name}
                              className="flex items-center justify-between rounded-xl border border-zinc-800 px-3 py-3"
                            >
                              <span className="text-sm text-white">{item.name}</span>
                              <span className="text-sm font-medium text-zinc-400">
                                {item.active_issue_count}
                              </span>
                            </div>
                          ))}
                          {linearWidgets.team_load.unassigned_count ? (
                            <div className="flex items-center justify-between rounded-xl border border-dashed border-zinc-800 px-3 py-3">
                              <span className="text-sm text-zinc-400">Unassigned</span>
                              <span className="text-sm font-medium text-zinc-400">
                                {linearWidgets.team_load.unassigned_count}
                              </span>
                            </div>
                          ) : null}
                        </div>
                      ) : (
                        <WidgetEmpty label="No active assignee load yet." />
                      )}
                    </DashboardWidgetShell>

                    <DashboardWidgetShell title="Active Issues" className="lg:col-span-2">
                      {linearWidgets?.active_issues.error ? (
                        <WidgetError label={linearWidgets.active_issues.error} />
                      ) : linearWidgets?.active_issues.items?.length ? (
                        <div className="space-y-3">
                          {linearWidgets.active_issues.items.map((item) => (
                            <div
                              key={item.id}
                              className="flex items-start justify-between gap-4 rounded-xl border border-zinc-800 px-4 py-3"
                            >
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-white">
                                  {item.identifier ? `${item.identifier} · ` : ""}
                                  {item.title}
                                </div>
                                <div className="mt-1 flex flex-wrap gap-3 text-xs text-zinc-500">
                                  {item.status && <span>{item.status}</span>}
                                  {item.assignee && <span>{item.assignee}</span>}
                                  {item.cycle && <span>{item.cycle}</span>}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <WidgetEmpty label="No active issues found." />
                      )}
                    </DashboardWidgetShell>

                    <DashboardWidgetShell title="Projects">
                      {linearWidgets?.projects.error ? (
                        <WidgetError label={linearWidgets.projects.error} />
                      ) : linearWidgets?.projects.items?.length ? (
                        <div className="space-y-3">
                          {linearWidgets.projects.items.map((project) => (
                            <div
                              key={project.id}
                              className="rounded-xl border border-zinc-800 px-3 py-3"
                            >
                              <div className="text-sm font-medium text-white">{project.name}</div>
                              <div className="mt-1 flex flex-wrap gap-3 text-xs text-zinc-500">
                                {project.state && <span>{project.state}</span>}
                                {project.lead && <span>{project.lead}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <WidgetEmpty label="No active projects found." />
                      )}
                    </DashboardWidgetShell>

                    <DashboardWidgetShell title="Top Labels">
                      {linearWidgets?.top_labels.error ? (
                        <WidgetError label={linearWidgets.top_labels.error} />
                      ) : linearWidgets?.top_labels.items?.length ? (
                        <div className="flex flex-wrap gap-2">
                          {linearWidgets.top_labels.items.map((label) => (
                            <span
                              key={label.id ?? label.name}
                              className="rounded-full border border-zinc-800 px-3 py-2 text-sm text-zinc-300"
                            >
                              {label.name}
                              {typeof label.count === "number" ? ` · ${label.count}` : ""}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <WidgetEmpty label="No label data available." />
                      )}
                    </DashboardWidgetShell>
                  </div>
                )}

                {loadingIntegrations ? (
                  <div className="rounded-2xl border border-zinc-800 bg-black p-6 text-sm text-zinc-400">
                    Loading integrations...
                  </div>
                ) : connectedIntegrations.length === 0 ? (
                  <div className="rounded-2xl border border-zinc-800 bg-black p-6">
                    <h3 className="text-base font-semibold text-white">
                      Add integrations to unlock analysis
                    </h3>
                    <p className="mt-2 text-sm text-zinc-400">
                      Connect at least one source like Amplitude, Zendesk, Productboard, or
                      Linear and Signal will generate your analysis automatically.
                    </p>
                    <div className="mt-4">
                      <Link
                        href="/connect"
                        className="inline-flex items-center rounded-xl border border-zinc-700 bg-white px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-zinc-200"
                      >
                        Connect integrations
                      </Link>
                    </div>
                  </div>
                ) : analysisLoading || agentRunning ? (
                  <div className="rounded-2xl border border-zinc-800 bg-black p-6 text-sm text-zinc-400">
                    Generating analysis from your connected integrations...
                  </div>
                ) : !analysisData || analysisData.status === "none" ? (
                  <div className="rounded-2xl border border-zinc-800 bg-black p-2">
                    {[
                      "Connect your tools",
                      "Set up your teams",
                      "Import your data",
                      "Get familiar with Linear",
                    ].map((item, index) => (
                      <div
                        key={item}
                        className={`px-6 py-7 text-[22px] font-medium text-white ${
                          index === 3 ? "bg-zinc-950" : ""
                        } ${index > 0 ? "border-t border-zinc-900" : ""}`}
                      >
                        {item}
                      </div>
                    ))}
                  </div>
                ) : hasSourceAnalysis ? (
                  <div ref={connectedToolsRef} className="space-y-4">
                    {connectedIntegrations
                      .map((key) => {
                        const analysisKey =
                          key === "amplitude"
                            ? "behavioral"
                            : key === "zendesk"
                            ? "support"
                            : key === "productboard"
                            ? "feature"
                            : key === "linear"
                            ? "execution"
                            : key;
                        const content = analysisData?.sources?.[analysisKey];
                        if (!content) return null;
                        return (
                          <div
                            key={key}
                            className="rounded-2xl border border-zinc-800 bg-black p-5"
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <h3 className="text-white font-semibold">
                                  {INTEGRATION_LABELS[key] ?? key}
                                </h3>
                                <p className="text-sm text-zinc-400 mt-1">
                                  {INTEGRATION_DESCRIPTIONS[key] ??
                                    "Integrated data source for analysis."}
                                </p>
                              </div>
                              <div className="text-xs text-emerald-400 font-medium">
                                Connected
                              </div>
                            </div>
                            <div className="mt-4 rounded-xl border border-zinc-800 bg-black p-4 text-sm text-zinc-200">
                              <div className="prose prose-invert prose-sm max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {content}
                                </ReactMarkdown>
                              </div>
                            </div>
                          </div>
                        );
                      })
                      .filter(Boolean)}

                    {analysisData?.sources?.["insights"] && (
                      <div className="rounded-2xl border border-zinc-800 bg-black p-5">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-white font-semibold">Customer Insights</h3>
                            <p className="text-sm text-zinc-400 mt-1">
                              Themes from uploaded customer interviews
                            </p>
                          </div>
                          <div className="text-xs text-emerald-400 font-medium">Morphik</div>
                        </div>
                        <div className="mt-4 rounded-xl border border-zinc-800 bg-black p-4 text-sm text-zinc-200">
                          <div className="prose prose-invert prose-sm max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {analysisData.sources["insights"]}
                            </ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : analysisData.brief ? (
                  <div
                    ref={latestBriefRef}
                    className="rounded-2xl border border-zinc-800 bg-black p-5"
                  >
                    <div className="prose prose-invert prose-sm max-w-none text-zinc-200">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {analysisData.brief}
                      </ReactMarkdown>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-zinc-800 bg-black p-6 text-sm text-zinc-400">
                    Analysis completed, but no renderable output was returned for this run.
                    Try refreshing or running the deep agent again.
                  </div>
                )}
              </div>
            )}

            {activeTab === "chat" && (
              <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-4">
                <aside className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">Chats</h3>
                    <button
                      onClick={startNewChat}
                      className="text-xs text-emerald-400 hover:text-emerald-300"
                    >
                      New
                    </button>
                  </div>
                  <div className="space-y-2">
                    {chatSessions.length === 0 && (
                      <div className="text-xs text-zinc-500">
                        No history yet.
                      </div>
                    )}
                    {chatSessions.map((session) => (
                      <button
                        key={session.id}
                        onClick={() => loadSession(session.id)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                          session.id === chatSessionId
                            ? "bg-emerald-500/15 text-emerald-200"
                            : "bg-zinc-950 text-zinc-300 hover:text-white hover:bg-zinc-800"
                        }`}
                      >
                        {getRenderedChatTitle(session, streamingChatTitles)}
                      </button>
                    ))}
                  </div>
                </aside>

                <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col min-h-[520px]">
                <div className="mb-4">
                  <h2 className="text-xl font-semibold">Product Chat</h2>
                  <p className="text-sm text-zinc-400">
                    Ask questions about your product data and trends.
                  </p>
                </div>
                <div className="flex-1 overflow-auto space-y-4 pr-2">
                  {chatLoadingHistory && (
                    <div className="text-sm text-zinc-500">Loading chat...</div>
                  )}
                  {chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                        msg.role === "user"
                          ? "bg-white text-black ml-auto"
                          : "bg-zinc-900/90 border border-zinc-800 text-zinc-100"
                      }`}
                    >
                      {msg.role === "assistant" ? (
                        <div>
                          {msg.isStreaming && (
                            <ChatActivityFeed message={msg} />
                          )}
                          {msg.content && (
                            <div className="prose prose-invert prose-sm max-w-none">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {msg.content}
                              </ReactMarkdown>
                            </div>
                          )}
                          {msg.status === "error" && !msg.content && (
                            <div className="text-sm text-red-400">
                              The chat request failed. Please try again.
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      )}
                      {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-zinc-500">
                          <span className="text-zinc-400">Sources</span>
                          {msg.sources.map((source) => (
                            <span
                              key={source}
                              className="rounded-full border border-zinc-700 px-2 py-0.5 text-zinc-300"
                            >
                              {source}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {chatError && (
                  <div className="mt-2 text-sm text-red-400">{chatError}</div>
                )}
                <div className="mt-4 flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask a question about your product..."
                    className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:border-zinc-500"
                    onKeyDown={(e) => e.key === "Enter" && !chatSending && sendMessage()}
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!chatInput.trim() || chatSending}
                    className="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {chatSending ? "Sending..." : "Send"}
                  </button>
                </div>
                </div>
              </div>
            )}

            {activeTab === "insights" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-semibold">Customer Insights</h2>
                    <p className="text-sm text-zinc-400">
                      Upload customer interview documents for analysis.
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-sm relative">
                    <button
                      onClick={() => setInsightsMenuOpen((prev) => !prev)}
                      className="px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 hover:text-white"
                    >
                      + New
                    </button>
                    {insightsMenuOpen && (
                      <div className="absolute right-24 top-10 z-20 w-52 rounded-xl border border-zinc-800 bg-zinc-950 shadow-lg">
                        <button
                          onClick={handleMenuCreateFolder}
                          className="w-full text-left px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800/60"
                        >
                          New folder
                        </button>
                        <label className="block px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800/60 cursor-pointer">
                          File upload
                          <input
                            type="file"
                            multiple
                            accept=".pdf,.doc,.docx,.ppt,.pptx,.ppsx,.xls,.xlsx,.xlsm,.txt,.md,.csv,.tsv,.json,.yaml,.yml,.xml,.html,.htm,.jpg,.jpeg,.png,.gif,.webp,.tiff,.bmp,.svg"
                            className="hidden"
                            onChange={(e) => {
                              setInsightsMenuOpen(false);
                              handleInsightsUpload(e.target.files);
                            }}
                          />
                        </label>
                        <label className="block px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800/60 cursor-pointer">
                          Folder upload
                          <input
                            ref={folderUploadRef}
                            type="file"
                            multiple
                            className="hidden"
                            onChange={(e) => {
                              setInsightsMenuOpen(false);
                              handleInsightsUpload(e.target.files);
                            }}
                          />
                        </label>
                      </div>
                    )}
                    <button
                      onClick={refreshInsights}
                      className="text-zinc-400 hover:text-white"
                      disabled={insightsRefreshing}
                    >
                      {insightsRefreshing ? "Refreshing..." : "Refresh"}
                    </button>
                    {insightsUploading && (
                      <span className="text-xs text-emerald-400">Uploading...</span>
                    )}
                  </div>
                </div>

                {insightsError && (
                  <div className="mb-3 text-sm text-red-400">{insightsError}</div>
                )}

                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-zinc-400">Folders</div>
                    <div className="text-xs text-zinc-500">
                      {activeFolder ? `Viewing: ${activeFolder}` : "All files"}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                    <button
                      onClick={() => setActiveFolder(null)}
                      className={`flex flex-col items-start gap-2 rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 text-left text-sm transition-colors ${
                        !activeFolder
                          ? "ring-1 ring-emerald-500/40"
                          : "hover:border-zinc-700"
                      }`}
                    >
                      <Image src="/Folder-1.png" alt="Folder" width={40} height={40} />
                      <span className="text-zinc-200">All files</span>
                    </button>
                    {insightsFolders.map((folder) => (
                      <button
                        key={folder.id}
                        onClick={() => setActiveFolder(folder.name)}
                        className={`flex flex-col items-start gap-2 rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 text-left text-sm transition-colors ${
                          activeFolder === folder.name
                            ? "ring-1 ring-emerald-500/40"
                            : "hover:border-zinc-700"
                        }`}
                      >
                        <Image src="/Folder-1.png" alt="Folder" width={40} height={40} />
                        <span className="text-zinc-200">{folder.name}</span>
                      </button>
                    ))}
                  </div>

                  <label
                    htmlFor="insights-drop"
                    className="block w-full rounded-xl border border-dashed border-zinc-700 bg-zinc-950/50 p-6 text-center text-sm text-zinc-400 cursor-pointer hover:border-zinc-500 transition-colors"
                  >
                    Drop PDFs here or click &quot;Upload files&quot; to add customer interviews.
                    <div className="mt-2 text-xs text-zinc-500">
                      Supports PDF, Word, PPT, Excel, images, and text files.
                    </div>
                    <input
                      id="insights-drop"
                      type="file"
                      multiple
                      accept=".pdf,.doc,.docx,.ppt,.pptx,.ppsx,.xls,.xlsx,.xlsm,.txt,.md,.csv,.tsv,.json,.yaml,.yml,.xml,.html,.htm,.jpg,.jpeg,.png,.gif,.webp,.tiff,.bmp,.svg"
                      className="hidden"
                      onChange={(e) => handleInsightsUpload(e.target.files)}
                    />
                  </label>

                    <div className="mt-2">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-semibold text-white">Files</h3>
                        <div className="text-xs text-zinc-500">
                          {activeFolder ? `Folder: ${activeFolder}` : "All files"} ·{" "}
                          {insightsDocs.length} items
                        </div>
                      </div>
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/50">
                      <div className="grid grid-cols-[1fr_140px_160px] gap-4 px-4 py-2 text-xs uppercase tracking-wider text-zinc-500 border-b border-zinc-800">
                        <div>Name</div>
                        <div>Status</div>
                        <div>Created</div>
                      </div>
                      {insightsDocs.length === 0 ? (
                        <div className="px-4 py-6 text-sm text-zinc-500">
                          {activeFolder
                            ? "No documents in this folder yet. Upload files while this folder is selected."
                            : "No documents yet."}
                        </div>
                      ) : (
                        <div className="divide-y divide-zinc-800">
                          {insightsDocs.map((doc) => (
                            <div
                              key={doc.document_id}
                              className="grid grid-cols-[1fr_140px_160px] gap-4 px-4 py-3 text-sm text-zinc-200 hover:bg-zinc-900/40"
                            >
                              <div className="flex items-center gap-3">
                                <Image
                                  src="/Folder-1.png"
                                  alt="File"
                                  width={24}
                                  height={24}
                                  className="opacity-70"
                                />
                                <div className="truncate">
                                  {doc.filename ??
                                    doc.name ??
                                    doc.metadata?.filename ??
                                    doc.document_id}
                                </div>
                              </div>
                              <div className="text-xs text-zinc-500">
                                {doc.status ?? "processing"}
                              </div>
                              <div className="text-xs text-zinc-500">
                                {doc.created_at ?? ""}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "builder" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-semibold">Build With An Coding Agent</h2>
                    <p className="text-sm text-zinc-400">
                      Vibe code with insights from your product data.
                    </p>
                  </div>
                  {codeSessionUrl && (
                    <div className="flex items-center gap-3 text-sm">
                      <button
                        onClick={() => setBuilderFullscreen(true)}
                        className="text-emerald-400 hover:text-emerald-300"
                      >
                        Full screen
                      </button>
                      <a
                        href={codeSessionUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-zinc-400 hover:text-white"
                      >
                        Open in new tab
                      </a>
                    </div>
                  )}
                </div>

                {codeSessionUrl ? (
                  <div className="relative rounded-2xl border border-zinc-800 bg-black/40 overflow-hidden w-full">
                    {!builderIframeLoaded && (
                      <div className="absolute inset-0 z-10 flex items-center justify-center bg-black">
                        <div className="flex flex-col items-center gap-4 text-center">
                          <div className="text-5xl animate-pulse">{"\u2699\ufe0f"}</div>
                          <div>
                            <div className="text-lg font-medium text-white">
                              Booting your IDE
                            </div>
                            <div className="mt-1 text-sm text-zinc-400">
                              The coding workspace is starting up.
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                    <iframe
                      src={codeSessionUrl}
                      className="w-full h-[calc(100vh-220px)]"
                      allow="clipboard-read; clipboard-write"
                      sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups allow-downloads"
                      title="VS Code Web Workbench"
                      onLoad={() => setBuilderIframeLoaded(true)}
                    />
                  </div>
                ) : codeSessionLoading ? (
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-10">
                    <div className="flex flex-col items-center gap-4 text-center">
                      <div className="text-5xl animate-pulse">{"\u2699\ufe0f"}</div>
                      <div>
                        <div className="text-lg font-medium text-white">
                          Booting your IDE
                        </div>
                        <div className="mt-1 text-sm text-zinc-400">
                          Connecting to the code workspace.
                        </div>
                      </div>
                    </div>
                  </div>
                ) : codeSessionError ? (
                  <div className="rounded-2xl border border-red-900/60 bg-red-950/20 p-6 text-sm text-red-300">
                    {codeSessionError}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-6 text-sm text-zinc-400">
                    Code workspace not available yet. Connect to the code service to
                    enable the embedded editor.
                  </div>
                )}

                {builderFullscreen && codeSessionUrl && (
                  <div className="fixed inset-0 z-50 bg-black/80">
                    <div className="absolute inset-4 rounded-2xl border border-zinc-800 bg-black overflow-hidden">
                      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-950/80">
                        <div className="text-sm text-zinc-300">VS Code Web</div>
                        <button
                          onClick={() => setBuilderFullscreen(false)}
                          className="text-sm text-zinc-400 hover:text-white"
                        >
                          Close
                        </button>
                      </div>
                      <div className="relative h-[calc(100%-40px)]">
                        {!builderIframeLoaded && (
                          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black">
                            <div className="flex flex-col items-center gap-4 text-center">
                              <div className="text-5xl animate-pulse">{"\u2699\ufe0f"}</div>
                              <div>
                                <div className="text-lg font-medium text-white">
                                  Booting your IDE
                                </div>
                                <div className="mt-1 text-sm text-zinc-400">
                                  The coding workspace is starting up.
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                        <iframe
                          src={codeSessionUrl}
                          className="w-full h-full"
                          allow="clipboard-read; clipboard-write"
                          sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups allow-downloads"
                          title="VS Code Web Workbench Fullscreen"
                          onLoad={() => setBuilderIframeLoaded(true)}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === "profile" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold">Profile</h2>
                  <Link
                    href="/connect"
                    className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
                  >
                    Manage integrations -&gt;
                  </Link>
                </div>
                <div className="space-y-3 text-sm text-zinc-300">
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                    <span className="text-zinc-400">User</span>
                    <span className="font-medium text-white">{user?.id ?? "Unknown"}</span>
                  </div>
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                    <span className="text-zinc-400">Connected integrations</span>
                    <span className="font-medium text-white">
                      {connectedIntegrations.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">Workspace</span>
                    <span className="font-medium text-white">Signal</span>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
        </div>
      </div>
      )}
    </main>
  );
}
