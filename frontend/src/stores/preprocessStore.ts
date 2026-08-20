import { useSyncExternalStore } from "react";
import { isTerminalStatus, type PreprocessDocument } from "../types/preprocess";

export interface PreprocessState {
  document: PreprocessDocument | null;
  pollingDocId: string | null;
  isPolling: boolean;
  isStarting: boolean;
  error: string | null;
}

const initialState: PreprocessState = {
  document: null,
  pollingDocId: null,
  isPolling: false,
  isStarting: false,
  error: null,
};

let state = initialState;
const listeners = new Set<() => void>();

function setState(nextState: Partial<PreprocessState>): void {
  state = { ...state, ...nextState };
  listeners.forEach((listener) => listener());
}

export const preprocessStore = {
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  getSnapshot(): PreprocessState {
    return state;
  },

  setStarting(isStarting: boolean): void {
    setState({ isStarting });
  },

  setStarted(document: PreprocessDocument): void {
    setState({
      document,
      pollingDocId: document.id,
      isPolling: true,
      error: null,
    });
  },

  updateDocument(document: PreprocessDocument): void {
    const completed = isTerminalStatus(document.status);
    setState({
      document,
      ...(completed && { pollingDocId: null, isPolling: false }),
    });
  },

  setPollingError(error: string): void {
    setState({ error, isPolling: false, pollingDocId: null });
  },

  stopPolling(): void {
    setState({ isPolling: false, pollingDocId: null });
  },

  reset(): void {
    state = initialState;
    listeners.forEach((listener) => listener());
  },
};

export function usePreprocessStore(): PreprocessState {
  return useSyncExternalStore(
    preprocessStore.subscribe,
    preprocessStore.getSnapshot,
    preprocessStore.getSnapshot,
  );
}