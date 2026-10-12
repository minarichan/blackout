import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { App } from "./App";
import { Overview } from "./pages/Overview";
import { PositionDetail } from "./pages/PositionDetail";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Overview />} />
          <Route path="book/:address" element={<Overview />} />
          <Route path="book/:address/position/:positionId" element={<PositionDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>,
);
