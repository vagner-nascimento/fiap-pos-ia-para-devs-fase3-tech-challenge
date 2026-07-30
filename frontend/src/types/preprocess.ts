export type PreprocessStatus =
  | "created"
  | "in_progress"
  | "completed"
  | "error";

export interface PreprocessDocument {
  id: string;
  train_data: number;
  rag_data: number;
  status: PreprocessStatus;
  updated_date: string;
  completion_percentage: number;
}

export interface PreprocessRequest {
  rag_percent?: number;
}

export const TERMINAL_STATUSES: PreprocessStatus[] = ["completed", "error"];

export function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as PreprocessStatus);
}
