"use client";

import Link from "next/link";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useClerk, useUser, UserButton } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import {
  createInsightsFolder,
  getIntegrations,
  getLatestAnalysis,
  getCodeSessionUrl,
  getStreamUrl,
  listChatMessages,
  listChatSessions,
  listCustomerDocs,
  listInsightsFolders,
  sendChat,
  startRun,
  uploadCustomerDocs,
} from "@/lib/api";

type TabKey = "analysis" | "chat" | "insights" | "builder" | "profile";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "analysis", label: "Deep Analysis" },
  { key: "chat", label: "Chat" },
  { key: "insights", label: "Customer Insights" },
  { key: "builder", label: "Build with Claude Code" },
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
};

type ChatSession = {
  id: string;
  title: string | null;
  updated_at?: string | null;
};

const SIDEBAR_MIN_WIDTH = 248;
const SIDEBAR_MAX_WIDTH = 380;
const SIDEBAR_DEFAULT_WIDTH = 288;
const SIDEBAR_PINNED_STORAGE_KEY = "signal-sidebar-pinned";
const SIDEBAR_WIDTH_STORAGE_KEY = "signal-sidebar-width";

export default function WorkspacePage() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("analysis");
  const [connected, setConnected] = useState<Record<string, boolean>>({});
  const [loadingIntegrations, setLoadingIntegrations] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [chatLoadingHistory, setChatLoadingHistory] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarPeekOpen, setSidebarPeekOpen] = useState(false);
  const [sidebarHovering, setSidebarHovering] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const [sidebarHydrated, setSidebarHydrated] = useState(false);
  const [builderFullscreen, setBuilderFullscreen] = useState(false);
  const [codeSessionUrl, setCodeSessionUrl] = useState("");
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
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Ask me anything about your product. I can summarize trends and signals.",
    },
  ]);
  const folderUploadRef = useRef<HTMLInputElement | null>(null);
  const autoRunAttemptedRef = useRef(false);
  const sidebarResizeStartRef = useRef({ x: 0, width: SIDEBAR_DEFAULT_WIDTH });

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
    if (!sidebarHovering && sidebarPeekOpen) {
      setSidebarPeekOpen(false);
    }
  }, [sidebarHovering, sidebarOpen, sidebarPeekOpen]);

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
        const data = await getCodeSessionUrl(user.id);
        if (mounted) setCodeSessionUrl(data.url);
      } catch (err) {
        console.error("Failed to fetch code session URL", err);
      }
    }
    if (isLoaded && user?.id) loadCodeSession();
    return () => {
      mounted = false;
    };
  }, [isLoaded, user]);

  useEffect(() => {
    let mounted = true;
    async function loadSessions() {
      if (!user) return;
      try {
        const sessions = await listChatSessions(user.id);
        if (mounted) setChatSessions(sessions);
      } catch {
        if (mounted) setChatSessions([]);
      }
    }
    loadSessions();
    return () => {
      mounted = false;
    };
  }, [user]);

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
    () => Object.keys(connected).filter((key) => connected[key]),
    [connected]
  );

  useEffect(() => {
    refreshAnalysis();
  }, [refreshAnalysis]);

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

  if (!isLoaded) {
    return (
      <main className="min-h-screen bg-[#0A0A0A] text-white flex items-center justify-center">
        <div className="text-sm text-zinc-400">Loading...</div>
      </main>
    );
  }

  async function sendMessage() {
    const content = chatInput.trim();
    if (!content) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content,
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatSending(true);
    setChatError("");

    try {
      if (!user) {
        throw new Error("Please sign in to chat.");
      }
      const payload = chatMessages
        .filter((msg) => msg.role === "user" || msg.role === "assistant")
        .map((msg) => ({ role: msg.role, content: msg.content }))
        .concat({ role: "user", content });
      const response = await sendChat(
        user.id,
        payload,
        chatSessionId ?? undefined,
        chatSessionId ? undefined : "Product chat",
        activeFolder ?? undefined
      );
      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: response.message,
        sources: response.sources_used,
      };
      if (!chatSessionId) {
        setChatSessionId(response.session_id);
      }
      setChatMessages((prev) => [...prev, assistantMsg]);
      const sessions = await listChatSessions(user.id);
      setChatSessions(sessions);
    } catch (err: unknown) {
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

  const isSidebarVisible = sidebarOpen || sidebarPeekOpen;
  const contentInset = SIDEBAR_DEFAULT_WIDTH + 48;
  const userBadge =
    user?.firstName?.[0]?.toUpperCase() ??
    user?.emailAddresses?.[0]?.emailAddress?.[0]?.toUpperCase() ??
    "S";
  const analysisSourceCount = Object.keys(analysisData?.sources ?? {}).length;
  const analysisReady =
    connectedIntegrations.length > 0 &&
    !!analysisData &&
    analysisData.status !== "none" &&
    analysisSourceCount > 0;

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
          className="mx-auto max-w-6xl"
          style={{ paddingLeft: contentInset }}
        >
        <div className="mb-5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                setSidebarOpen((current) => !current);
                setSidebarPeekOpen(false);
              }}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-zinc-800 bg-black text-zinc-300 hover:border-zinc-700 hover:text-white"
              aria-label={sidebarOpen ? "Close menu" : "Open menu"}
            >
              {sidebarOpen ? "←" : "≡"}
            </button>
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.24em] text-zinc-500">
                StarSignals Workspace
              </div>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">
                Product intelligence
              </h1>
              <p className="mt-1 text-sm text-zinc-500">
                Connected signals, analysis, and workspace tools in one place.
              </p>
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
            className="fixed left-0 top-0 bottom-0 z-20 w-8"
            onMouseEnter={() => {
              setSidebarHovering(true);
              if (!sidebarOpen) setSidebarPeekOpen(true);
            }}
            onMouseLeave={() => {
              setSidebarHovering(false);
              if (!sidebarOpen) setSidebarPeekOpen(false);
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
            className="fixed left-4 top-[92px] bottom-6 z-30 overflow-hidden rounded-[24px] border border-zinc-800 bg-black shadow-[0_18px_50px_rgba(0,0,0,0.35)] transition-transform duration-300 ease-out"
            style={{
              width: sidebarWidth,
              transform: isSidebarVisible
                ? "translateX(0)"
                : "translateX(calc(-100% - 24px))",
            }}
          >
            <div className="flex h-full flex-col">
              <div className="border-b border-zinc-800 px-4 py-4">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-zinc-100 text-base font-semibold text-black">
                      {userBadge}
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-lg font-semibold text-white">
                        StarSignals
                      </div>
                      <div className="truncate text-xs text-zinc-500">
                        PM operating system
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSidebarOpen((current) => !current)}
                      className="flex h-10 w-10 items-center justify-center rounded-2xl border border-zinc-800 bg-black text-sm text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
                      aria-label={sidebarOpen ? "Collapse sidebar" : "Pin sidebar"}
                    >
                      {sidebarOpen ? "←" : "→"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-3 py-4">
                <div className="px-3 text-xs uppercase tracking-[0.22em] text-zinc-600">
                  Workspace
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
                            ? "bg-black text-white"
                            : "text-zinc-400 hover:bg-black hover:text-white"
                        }`}
                      >
                        <span>{tab.label}</span>
                        <span className="text-xs text-zinc-600">›</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <button
                onMouseDown={(event) => {
                  if (!sidebarOpen) return;
                  sidebarResizeStartRef.current = {
                    x: event.clientX,
                    width: sidebarWidth,
                  };
                  setIsResizingSidebar(true);
                }}
                className={`absolute right-0 top-0 h-full w-3 cursor-ew-resize transition-opacity ${
                  sidebarOpen ? "opacity-100" : "opacity-0"
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
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-white">Deep Analysis</h2>
                    <p className="mt-1 text-sm text-zinc-500">
                      Signals collected from your connected product stack.
                    </p>
                  </div>
                  <button
                    onClick={refreshAnalysis}
                    className="rounded-xl border border-zinc-800 bg-black px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-700 hover:text-white"
                  >
                    Refresh
                  </button>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl border border-zinc-800 bg-black p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Sources</div>
                    <div className="mt-2 text-2xl font-semibold text-white">
                      {connectedIntegrations.length}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-zinc-800 bg-black p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Status</div>
                    <div className="mt-2 text-2xl font-semibold text-white">
                      {analysisReady ? "Ready" : connectedIntegrations.length === 0 ? "Setup" : "Running"}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-zinc-800 bg-black p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Coverage</div>
                    <div className="mt-2 text-2xl font-semibold text-white">
                      {analysisSourceCount}
                    </div>
                  </div>
                </div>

                {agentRunning && (
                  <div className="flex flex-wrap gap-3 rounded-2xl border border-zinc-800 bg-black p-4">
                    {[
                      { key: "behavioral", label: "Amplitude", integration: "amplitude" },
                      { key: "support", label: "Zendesk", integration: "zendesk" },
                      { key: "feature", label: "Productboard", integration: "productboard" },
                      { key: "execution", label: "Linear", integration: "linear" },
                      { key: "insights", label: "Customer Insights", integration: null },
                    ].filter(({ integration }) => integration === null || connected[integration])
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
                ) : (
                  <div className="space-y-4">
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
                        {session.title ?? "Untitled chat"}
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
                        <div className="prose prose-invert prose-sm max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
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
                    <h2 className="text-xl font-semibold">Build with Claude Code</h2>
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
                  <div className="rounded-2xl border border-zinc-800 bg-black/40 overflow-hidden w-full">
                    <iframe
                      src={codeSessionUrl}
                      className="w-full h-[calc(100vh-220px)]"
                      allow="clipboard-read; clipboard-write"
                      sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups allow-downloads"
                      title="VS Code Web Workbench"
                    />
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
                      <iframe
                        src={codeSessionUrl}
                        className="w-full h-[calc(100%-40px)]"
                        allow="clipboard-read; clipboard-write"
                        sandbox="allow-same-origin allow-scripts allow-forms allow-modals allow-popups allow-downloads"
                        title="VS Code Web Workbench Fullscreen"
                      />
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
