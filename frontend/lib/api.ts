const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type IntegrationCredentialField = {
  name: string;
  label: string;
  kind: "text" | "password" | "url";
  placeholder: string;
  required: boolean;
};

export type IntegrationProvider = {
  id: string;
  label: string;
  category: string;
  description: string;
  status: "supported" | "blocked" | "existing_non_mcp";
  surfaces: string[];
  auth_mode: "token" | "json_credentials" | "oauth_future" | "oauth";
  transport: "streamable_http" | "stdio" | "custom";
  credential_schema: IntegrationCredentialField[];
  logo_path?: string | null;
  reason_unavailable?: string | null;
  chat_enabled: boolean;
  pipeline_enabled: boolean;
  builder_key?: string | null;
  connectable: boolean;
};

export type IntegrationCatalogGroup = {
  category: string;
  providers: IntegrationProvider[];
};

export type IntegrationStatus = {
  connected: boolean;
  status: string;
  label?: string;
  connectable?: boolean;
  pipeline_enabled?: boolean;
};

export type LinearDashboardResponse = {
  connected: boolean;
  refreshed_at: string;
  widgets?: {
    active_issues: {
      items?: Array<{
        id: string;
        identifier?: string;
        title: string;
        status?: string;
        assignee?: string;
        cycle?: string;
      }>;
      error?: string;
    };
    cycle_progress: {
      active_cycle?: {
        id?: string;
        name: string;
        starts_at?: string;
        ends_at?: string;
      } | null;
      counts?: {
        backlog: number;
        active: number;
        blocked: number;
        done: number;
        other: number;
        total: number;
      };
      completion_pct?: number | null;
      error?: string;
    };
    projects: {
      items?: Array<{
        id: string;
        name: string;
        state?: string;
        lead?: string;
      }>;
      error?: string;
    };
    issue_status_breakdown: {
      counts?: {
        backlog: number;
        active: number;
        blocked: number;
        done: number;
        other: number;
      };
      error?: string;
    };
    top_labels: {
      items?: Array<{
        id?: string;
        name: string;
        count?: number;
      }>;
      error?: string;
    };
    team_load: {
      items?: Array<{
        id?: string;
        name: string;
        active_issue_count: number;
      }>;
      unassigned_count?: number;
      error?: string;
    };
  };
};

export async function connectIntegration(
  userId: string,
  integrationType: string,
  credentials: string | Record<string, string>
): Promise<void> {
  const body =
    typeof credentials === "string"
      ? {
          user_id: userId,
          integration_type: integrationType,
          token: credentials,
        }
      : {
          user_id: userId,
          integration_type: integrationType,
          credentials,
        };
  const res = await fetch(`${API_URL}/integrations/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getIntegrationCatalog(): Promise<{
  groups: IntegrationCatalogGroup[];
}> {
  const res = await fetch(`${API_URL}/integrations/catalog`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getIntegrations(
  userId: string
): Promise<Record<string, IntegrationStatus>> {
  const res = await fetch(`${API_URL}/integrations/${userId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getSlackConnectUrl(
  userId: string,
  access: "public" | "private" = "public"
): string {
  const url = new URL(`${API_URL}/slack/connect`);
  url.searchParams.set("user_id", userId);
  url.searchParams.set("access", access);
  return url.toString();
}

export async function getCodeSessionUrl(
  userId: string
): Promise<{ url: string; expires_at: number }> {
  const url = new URL(`${API_URL}/code/session`);
  url.searchParams.set("user_id", userId);
  const res = await fetch(url.toString(), { credentials: "include" });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  if (data?.url && typeof data.url === "string") {
    const absoluteUrl = data.url.startsWith("/")
      ? `${API_URL}${data.url}`
      : data.url;
    if (data?.token && typeof data.token === "string") {
      const parsed = new URL(absoluteUrl);
      parsed.searchParams.set("token", data.token);
      data.url = parsed.toString();
    } else {
      data.url = absoluteUrl;
    }
  }
  return data;
}

export async function startRun(
  userId: string,
  hypothesis: string,
  productArea: string
): Promise<string> {
  const res = await fetch(`${API_URL}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      hypothesis,
      product_area: productArea,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.run_id;
}

export function getStreamUrl(runId: string): string {
  return `${API_URL}/run/${runId}/stream`;
}

export async function sendChat(
  userId: string,
  messages: Array<{ role: "user" | "assistant"; content: string }>,
  sessionId?: string,
  title?: string,
  folderName?: string
): Promise<{ message: string; sources_used: string[]; session_id: string }> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      messages,
      session_id: sessionId ?? null,
      title: title ?? null,
      folder_name: folderName ?? null,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

type StreamChatEvent =
  | { type: "thinking_start"; session_id: string }
  | { type: "activity_step"; session_id: string; step_id: string; label: string; status: "active" | "complete" }
  | { type: "activity_complete"; session_id: string; summary: string; tool_count: number }
  | { type: "final_response"; session_id: string; message: string; sources_used: string[] }
  | { type: "done"; session_id: string }
  | { type: "error"; session_id?: string; message: string };

type StreamChatHandlers = {
  onEvent: (event: StreamChatEvent) => void;
};

function createSseEventParser(onEvent: (event: StreamChatEvent) => void) {
  let buffer = "";
  return (chunk: string) => {
    buffer += chunk;
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const dataLines = part
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim());
      if (!dataLines.length) continue;
      const payload = dataLines.join("\n");
      onEvent(JSON.parse(payload) as StreamChatEvent);
    }
  };
}

export async function streamChat(
  userId: string,
  messages: Array<{ role: "user" | "assistant"; content: string }>,
  sessionId?: string,
  title?: string,
  folderName?: string,
  handlers?: StreamChatHandlers
): Promise<void> {
  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      messages,
      session_id: sessionId ?? null,
      title: title ?? null,
      folder_name: folderName ?? null,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  if (!res.body) throw new Error("No response stream returned.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const handleChunk = createSseEventParser((event) => handlers?.onEvent(event));

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    handleChunk(decoder.decode(value, { stream: true }));
  }
  handleChunk(decoder.decode());
}

export async function startChatSession(
  userId: string,
  firstMessage: string,
  title = "Product chat"
): Promise<{ session_id: string; title: string }> {
  const res = await fetch(`${API_URL}/chat/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      first_message: firstMessage,
      title,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listChatSessions(
  userId: string
): Promise<Array<{ id: string; title: string | null; updated_at: string | null }>> {
  const res = await fetch(`${API_URL}/chat/sessions/${userId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listChatMessages(
  sessionId: string
): Promise<
  Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    sources_used: string[];
  }>
> {
  const res = await fetch(`${API_URL}/chat/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getChatTitleStreamUrl(sessionId: string): string {
  return `${API_URL}/chat/sessions/${sessionId}/title-stream`;
}

export async function getLatestAnalysis(
  userId: string
): Promise<{
  run_id: string | null;
  status: string;
  brief: string | null;
  sources: Record<string, string>;
}> {
  const res = await fetch(`${API_URL}/run/latest/${userId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRunAnalysisSource(
  runId: string,
  agentKey: string
): Promise<{
  run_id: string;
  agent_key: string;
  content: string | null;
}> {
  const res = await fetch(`${API_URL}/run/${runId}/source/${agentKey}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getLinearDashboard(
  userId: string
): Promise<LinearDashboardResponse> {
  const res = await fetch(`${API_URL}/dashboard/linear/${userId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadCustomerDocs(
  userId: string,
  files: File[],
  folderName?: string
): Promise<{ uploaded: Array<{ document_id?: string; status?: string }> }> {
  const form = new FormData();
  form.append("user_id", userId);
  if (folderName) form.append("folder_name", folderName);
  files.forEach((file) => form.append("files", file));
  const res = await fetch(`${API_URL}/insights/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listCustomerDocs(
  userId: string,
  folderName?: string
): Promise<{
  documents: Array<{
    document_id: string;
    name?: string;
    created_at?: string;
    status?: string;
    folder_name?: string;
    metadata?: Record<string, string>;
  }>;
  total_count?: number;
}> {
  const url = new URL(`${API_URL}/insights/list/${userId}`);
  if (folderName) url.searchParams.set("folder_name", folderName);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createInsightsFolder(
  userId: string,
  name: string
): Promise<{ id: string; name: string; created_at?: string }> {
  const form = new FormData();
  form.append("user_id", userId);
  form.append("name", name);
  const res = await fetch(`${API_URL}/insights/folders`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listInsightsFolders(
  userId: string
): Promise<Array<{ id: string; name: string; created_at?: string }>> {
  const res = await fetch(`${API_URL}/insights/folders/${userId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
