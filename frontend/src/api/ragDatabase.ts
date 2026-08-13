import { apiFetch } from "./client";
import type { RagGenerationDocument, RagGenerationRequest } from "../types/ragDatabase";

export function startRagGeneration(
  request: RagGenerationRequest,
): Promise<RagGenerationDocument> {
  return apiFetch<RagGenerationDocument>("/rag-database/", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
