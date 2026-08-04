export interface LossHistoryEntry {
  step: number;
  epoch: number | null;
  loss: number;
  kind?: "eval_loss";
  timestamp: string;
}

export interface PreprocessSnapshot {
  _id: string;
  status: string;
  rag_percent: number;
  updated_date: string;
}

export interface FineTuningDocument {
  _id: string;
  preprocess_id: string;
  preprocess_snapshot: PreprocessSnapshot;
  base_model_name: string;
  qas_train_path: string;
  clinical_protocols_train_path: string;
  model_output_dir: string;
  tokenizer_output_dir: string;
  summary_path: string;
  include_clinical_protocols: boolean;
  use_4bit_requested: boolean;
  use_4bit_effective: boolean | null;
  status: "pendding" | "in_progress" | "completed" | "error";
  completion_percentage: number;
  error_message: string | null;
  created_date: string;
  updated_date: string;
  started_date: string | null;
  finished_date: string | null;
  device: string | null;
  dataset_size: number;
  qas_examples: number;
  clinical_protocol_examples: number;
  estimated_total_steps: number;
  current_step: number;
  current_epoch: number | null;
  current_loss: number | null;
  loss_history: LossHistoryEntry[];
  training_metrics: Record<string, unknown>;
  max_seq_length: number;
  num_train_epochs: number;
  per_device_train_batch_size: number;
  gradient_accumulation_steps: number;
  learning_rate: number;
  warmup_ratio: number;
  logging_steps: number;
  seed: number;
}

export interface FineTuningRequest {
  preprocess_id: string;
  base_model_name?: string;
  include_clinical_protocols?: boolean;
  use_4bit?: boolean;
  max_seq_length?: number;
  num_train_epochs?: number;
  per_device_train_batch_size?: number;
  gradient_accumulation_steps?: number;
  learning_rate?: number;
  warmup_ratio?: number;
  logging_steps?: number;
  seed?: number;
}
