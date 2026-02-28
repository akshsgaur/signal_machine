const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function connectIntegration(
  userId: string,
  integrationType: string,
  token: string
): Promise<void> {
  const res = await fetch(`${API_URL}/integrations/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      integration_type: integrationType,
      token,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function getIntegrations(
  userId: string
): Promise<Record<string, boolean>> {
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
  if (data?.token && typeof data.token === "string" && !data.url?.includes("token=")) {
    data.url = `${data.url}${data.url.includes("?") ? "&" : "?"}token=${data.token}`;
  }
  if (data?.url && typeof data.url === "string" && data.url.startsWith("/")) {
    data.url = `${API_URL}${data.url}`;
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
