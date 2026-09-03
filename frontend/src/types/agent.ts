export interface AgentChatRequest {
  query: string;
  session_id?: string;
  preprocess_id?: string | null;
}

export interface AgentSource {
  dataset: string;
  source_type: string;
  similarity_score: number;
  content_preview: string;
}

export interface AgentChatResponse {
  session_id: string;
  response: string;
  sources: AgentSource[];
  sources_cited: string[];
  topic_valid: boolean;
  safety_triggered: boolean;
  safety_reason: string | null;
  requires_human_validation: boolean;
  audit_id: string;
  duration_ms: number;
}
