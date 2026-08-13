export type RagGenerationStatus = "pendding" | "in_progress" | "completed" | "error";

export interface RagGenerationSnapshot {
  _id: string;
  status: string;
  rag_percent: number;
  updated_date: string;
}

export interface RagGenerationDocument {
  id: string;
  _id?: string;
  batch_id: string;
  preprocess_id: string;
  preprocess_snapshot: RagGenerationSnapshot;
  qas_rag_path: string;
  clinical_protocols_rag_path: string;
  embedding_model: string;
  splitter_name: string;
  splitter_chunk_size: number;
  splitter_chunk_overlap: number;
  status: RagGenerationStatus;
  completion_percentage: number;
  error_message: string | null;
  created_date: string;
  updated_date: string;
  started_date: string | null;
  finished_date: string | null;
  current_step: number;
  estimated_total_steps: number;
  qas_documents: number;
  clinical_protocol_documents: number;
  total_documents: number;
}

export interface RagGenerationRequest {
  preprocess_id: string;
}

export const TERMINAL_RAG_STATUSES: RagGenerationStatus[] = ["completed", "error"];

export function isTerminalRagStatus(status: string): boolean {
  return TERMINAL_RAG_STATUSES.includes(status as RagGenerationStatus);
}
