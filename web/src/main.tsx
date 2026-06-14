import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { applyReadingPreferences, loadReadingPreferences } from "./readingPreferences";
import "./styles.css";

applyReadingPreferences(loadReadingPreferences());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
