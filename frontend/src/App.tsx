import { useState } from "react";
import { Layout } from "./components/Layout";
import { PreProcessingPage } from "./pages/PreProcessingPage";

type MenuItem = "pre-processing";

function App() {
  const [activeMenu, setActiveMenu] = useState<MenuItem>("pre-processing");

  return (
    <Layout activeMenu={activeMenu} onMenuChange={setActiveMenu}>
      {activeMenu === "pre-processing" && <PreProcessingPage />}
    </Layout>
  );
}

export default App;
