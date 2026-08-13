import { useState } from "react";
import { Layout } from "./components/Layout";
import { PreProcessingPage } from "./pages/PreProcessingPage";
import { RagGenerationPage } from "./pages/RagGenerationPage";

type View = "preprocess" | "rag_generation";

function App() {
  const [activeView, setActiveView] = useState<View>("preprocess");
  const [lastPreprocessId, setLastPreprocessId] = useState<string | null>(null);

  return (
    <Layout activeView={activeView} onNavigate={setActiveView}>
      {activeView === "preprocess" && (
        <PreProcessingPage onPreprocessComplete={setLastPreprocessId} />
      )}

      {activeView === "rag_generation" && (
        <RagGenerationPage lastPreprocessId={lastPreprocessId} />
      )}
    </Layout>
  );
}

export default App;
