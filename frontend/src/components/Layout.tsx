import type { ReactNode } from "react";
import "./Layout.css";

interface LayoutProps {
  children: ReactNode;
  activeView: "preprocess" | "rag_generation";
  onNavigate: (view: "preprocess" | "rag_generation") => void;
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
        </nav>
      </aside>

      <main className="content">{children}</main>
    </div>
  );
}
