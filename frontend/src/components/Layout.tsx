import type { ReactNode } from "react";
import "./Layout.css";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          FIAP POS IA
          <span>Fase 3 - Tech Challenge</span>
        </div>

        <nav className="nav" aria-label="Menu lateral">
          <button type="button" className="nav-item active" disabled>
            Pre Processing
          </button>
        </nav>
      </aside>

      <main className="content">{children}</main>
    </div>
  );
}
