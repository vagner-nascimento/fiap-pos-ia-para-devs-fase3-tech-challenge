import { apiFetch } from "./client";
import type { AgentChatRequest, AgentChatResponse } from "../types/agent";

const AGENT_API_URL =
  import.meta.env.VITE_AGENT_URL?.replace(/\/$/, "") ?? "http://localhost:8001";

export function chatWithAgent(request: AgentChatRequest): Promise<AgentChatResponse> {
  return apiFetch<AgentChatResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify(request),
  }, AGENT_API_URL);
}
