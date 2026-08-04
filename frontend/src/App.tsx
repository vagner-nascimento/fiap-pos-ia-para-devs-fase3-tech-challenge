import { useState } from "react";
import { Layout } from "./components/Layout";
import { PreProcessingPage } from "./pages/PreProcessingPage";
import { FineTuningPage } from "./pages/FineTuningPage";

type MenuItem = "pre-processing" | "fine-tuning";

function App() {
  const [activeMenu, setActiveMenu] = useState<MenuItem>("pre-processing");
  const [lastPreprocessId, setLastPreprocessId] = useState<string | null>(null);

  return (
    <Layout activeMenu={activeMenu} onMenuChange={setActiveMenu}>
      {activeMenu === "pre-processing" && (
        <PreProcessingPage onPreprocessComplete={setLastPreprocessId} />
      )}
      {activeMenu === "fine-tuning" && (
        <FineTuningPage lastPreprocessId={lastPreprocessId} />
      )}
    </Layout>
  );
}

export default App;
