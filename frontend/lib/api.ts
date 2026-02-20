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
