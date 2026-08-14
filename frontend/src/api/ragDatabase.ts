import { apiFetch } from "./client";
import type {
  RagGenerationDocument,
  RagGenerationRequest,
  RagQueryRequest,
  RagQueryResponse,
} from "../types/ragDatabase";

export function startRagGeneration(
  request: RagGenerationRequest,
): Promise<RagGenerationDocument> {
  return apiFetch<RagGenerationDocument>("/rag-database/", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function queryRagDatabase(
  request: RagQueryRequest,
): Promise<RagQueryResponse> {
  return apiFetch<RagQueryResponse>("/rag-database/query", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

