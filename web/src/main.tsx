// Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
// Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
// Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { I18nProvider } from "./i18n";
import { AsoPage } from "./pages/AsoPage";
import { ComparePage } from "./pages/ComparePage";
import { CriteriaPage } from "./pages/CriteriaPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { KeysPage } from "./pages/KeysPage";
import { PlanPage } from "./pages/PlanPage";
import { ReportPage } from "./pages/ReportPage";
import "./styles/tokens.css";
import "./styles/app.css";

const router = createBrowserRouter(
  [
    { path: "/", element: <HomePage /> },
    { path: "/audits/:auditId", element: <ReportPage /> },
    { path: "/audits/:auditId/report", element: <CriteriaPage /> },
    { path: "/audits/:auditId/plan", element: <PlanPage /> },
    { path: "/audits/:auditId/aso", element: <AsoPage /> },
    { path: "/audits/:auditId/history", element: <HistoryPage /> },
    { path: "/audits/:auditId/compare", element: <ComparePage /> },
    { path: "/keys", element: <KeysPage /> },
  ],
  { future: { v7_relativeSplatPath: true } },
);

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("#root introuvable");

createRoot(rootEl).render(
  <StrictMode>
    <I18nProvider>
      <RouterProvider router={router} />
    </I18nProvider>
  </StrictMode>,
);
