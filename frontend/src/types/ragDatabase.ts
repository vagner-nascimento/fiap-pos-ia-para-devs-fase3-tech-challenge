export type RagGenerationStatus = "completed" | "error";

export interface RagGenerationPreprocessSnapshot {
  _id: string;
  status: string;
  rag_percent?: number | null;
  updated_date?: string | null;
}

export interface RagGenerationDocument {
  id: string;
  batch_id: string;
  preprocess_id: string;
  preprocess_snapshot: RagGenerationPreprocessSnapshot;
  qas_rag_path: string;
  clinical_protocols_rag_path: string;
  embedding_model: string;
  splitter_name: string;
  splitter_chunk_size: number;
  splitter_chunk_overlap: number;
  status: RagGenerationStatus;
  error_message: string | null;
  created_date: string;
  updated_date: string;
  qas_documents: number;
  clinical_protocol_documents: number;
  total_documents: number;
}

export interface RagGenerationRequest {
  preprocess_id: string;
}
