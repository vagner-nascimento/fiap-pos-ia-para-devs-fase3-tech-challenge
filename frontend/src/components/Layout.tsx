import type { ReactNode } from "react";
import "./Layout.css";

export type ViewType = "agent" | "preprocess" | "rag_generation" | "rag_query";

interface LayoutProps {
  children: ReactNode;
  activeView: ViewType;
  onNavigate: (view: ViewType) => void;
}

export function Layout({ children, activeView, onNavigate }: LayoutProps) {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          FIAP POS IA
          <span>Fase 3 - Tech Challenge</span>
        </div>

        <nav className="nav" aria-label="Menu lateral">
          <button
            type="button"
            className={`nav-item ${activeView === "preprocess" ? "active" : ""}`}
            onClick={() => onNavigate("preprocess")}
          >
            Pre Processing
          </button>
          <button
            type="button"
            className={`nav-item ${activeView === "rag_generation" ? "active" : ""}`}
            onClick={() => onNavigate("rag_generation")}
          >
            RAG Generation
          </button>
          <button
            type="button"
            className={`nav-item ${activeView === "rag_query" ? "active" : ""}`}
            onClick={() => onNavigate("rag_query")}
          >
            RAG Query
          </button>
          <button
            type="button"
            className={`nav-item ${activeView === "agent" ? "active" : ""}`}
            onClick={() => onNavigate("agent")}
          >
            Assistente Médico
          </button>
        </nav>
      </aside>


      <main className="content">{children}</main>
    </div>
  );
}
