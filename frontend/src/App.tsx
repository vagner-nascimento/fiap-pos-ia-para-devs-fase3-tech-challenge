import { useState } from "react";
import { Layout, type ViewType } from "./components/Layout";
import { AgentPage } from "./pages/AgentPage";
import { PreProcessingPage } from "./pages/PreProcessingPage";
import { RagGenerationPage } from "./pages/RagGenerationPage";
import { RagQueryPage } from "./pages/RagQueryPage";

function App() {
  const [activeView, setActiveView] = useState<ViewType>("agent");
  const [lastPreprocessId, setLastPreprocessId] = useState<string | null>(null);

  return (
    <Layout activeView={activeView} onNavigate={setActiveView}>
      {activeView === "agent" && <AgentPage />}
      {activeView === "preprocess" && (
        <PreProcessingPage onPreprocessComplete={setLastPreprocessId} />
      )}

      {activeView === "rag_generation" && (
        <RagGenerationPage lastPreprocessId={lastPreprocessId} />
      )}

      {activeView === "rag_query" && (
        <RagQueryPage lastPreprocessId={lastPreprocessId} />
      )}
    </Layout>
  );
}


export default App;
