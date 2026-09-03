const API_BASE_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") ?? "http://localhost:3000";

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg: string }[] };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).join(", ");
    }
  } catch {
    // ignore parse errors
  }
  return `Erro HTTP ${response.status}`;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  baseUrl: string = API_BASE_URL,
): Promise<T> {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json() as Promise<T>;
}
