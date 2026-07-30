import { useEffect, useRef } from "react";
import { getPreprocessStatus } from "../api/preprocess";
import { isTerminalStatus, type PreprocessDocument } from "../types/preprocess";

const POLL_INTERVAL_MS = 2000;

interface UsePreprocessPollingOptions {
  docId: string | null;
  enabled: boolean;
  onUpdate: (document: PreprocessDocument) => void;
  onError: (message: string) => void;
  onComplete: () => void;
}

export function usePreprocessPolling({
  docId,
  enabled,
  onUpdate,
  onError,
  onComplete,
}: UsePreprocessPollingOptions): void {
  const callbacksRef = useRef({ onUpdate, onError, onComplete });

  useEffect(() => {
    callbacksRef.current = { onUpdate, onError, onComplete };
  });

  useEffect(() => {
    if (!docId || !enabled) {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      if (cancelled) {
        return;
      }

      try {
        const document = await getPreprocessStatus(docId);
        if (cancelled) {
          return;
        }

        callbacksRef.current.onUpdate(document);

        if (isTerminalStatus(document.status)) {
          callbacksRef.current.onComplete();
          return;
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        const message =
          error instanceof Error ? error.message : "Erro ao consultar status";
        callbacksRef.current.onError(message);
        callbacksRef.current.onComplete();
        return;
      }

      timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
      }
    };
  }, [docId, enabled]);
}
