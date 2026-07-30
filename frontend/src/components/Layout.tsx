import type { ReactNode } from "react";
import "./Layout.css";

type MenuItem = "pre-processing";

interface LayoutProps {
  activeMenu: MenuItem;
  onMenuChange: (menu: MenuItem) => void;
  children: ReactNode;
}

export function Layout({ activeMenu, onMenuChange, children }: LayoutProps) {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          FIAP POS IA
          <span>Fase 3 — Tech Challenge</span>
        </div>

        <nav className="nav">
          <button
            type="button"
            className={`nav-item${activeMenu === "pre-processing" ? " active" : ""}`}
            onClick={() => onMenuChange("pre-processing")}
          >
            Pre Processing
          </button>
        </nav>
      </aside>

      <main className="content">{children}</main>
    </div>
  );
}
