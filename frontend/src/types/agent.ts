export interface AgentChatRequest {
  query: string;
  session_id?: string;
  preprocess_id?: string | null;
  patient_name?: string | null;
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
  patient_context_used?: boolean;
  patient_fields_used?: string[];
  context_summarized?: boolean;
  audit_id: string;
  duration_ms: number;
}

export interface AuditRagDocument {
  id?: string;
  dataset?: string;
  source_type?: string;
  similarity_score?: number;
  content_preview?: string;
}

export interface AgentAuditLog {
  id: string;
  session_id: string;
  query: string;
  topic_valid: boolean;
  safety_triggered: boolean;
  safety_reason: string | null;
  rag_documents_count: number;
  rag_documents_used: AuditRagDocument[];
  llm_response_raw: string;
  sources_cited: string[];
  has_disclaimer: boolean;
  preprocess_id: string | null;
  duration_ms: number;
  patient_record_used?: boolean;
  patient_fields_used?: string[];
  context_summarized?: boolean;
  context_summarizer_mode?: string;
  created_date: string;
  final_response: string;
}

export interface AgentConversationTurn {
  query: string;
  response: string;
  sources: AgentSource[];
  safety_triggered: boolean;
  safety_reason: string | null;
  patient_name?: string | null;
  patient_context_used?: boolean;
  patient_fields_used?: string[];
}
