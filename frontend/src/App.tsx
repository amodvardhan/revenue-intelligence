import type { ReactNode } from "react";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AppSidebar } from "@/components/shared/AppSidebar";
import { setAuthToken } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ImportPage } from "./pages/ImportPage";
import { LoginPage } from "./pages/LoginPage";
import { CustomerSegmentsPage } from "./pages/CustomerSegmentsPage";
import { ForecastingPage } from "./pages/ForecastingPage";
import { EnterpriseGovernancePage } from "./pages/EnterpriseGovernancePage";
import { FxRatesPage } from "./pages/FxRatesPage";
import { HubSpotIntegrationPage } from "./pages/HubSpotIntegrationPage";
import { ProfitabilityPage } from "./pages/ProfitabilityPage";
import { NLQueryAuditLogPage } from "./pages/NLQueryAuditLogPage";
import { NLQueryPage } from "./pages/NLQueryPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DeliveryManagersPage } from "./pages/DeliveryManagersPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { TeamUsersPage } from "./pages/TeamUsersPage";
import { RevenuePage } from "./pages/RevenuePage";

const phase6 = import.meta.env.VITE_ENABLE_PHASE6 === "true";

function Shell() {
  return (
    <div className="flex h-screen min-h-0 overflow-hidden bg-sidebar">
      <AppSidebar />
      <main className="app-shell-main relative min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain">
        <Outlet />
      </main>
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function App() {
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route path="/import" element={<ImportPage />} />
          <Route path="/revenue" element={<RevenuePage />} />
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/delivery-managers" element={<DeliveryManagersPage />} />
          <Route path="/team/users" element={<TeamUsersPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/ask" element={<NLQueryPage />} />
          <Route path="/query-audit" element={<NLQueryAuditLogPage />} />
          <Route path="/integrations/hubspot" element={<HubSpotIntegrationPage />} />
          <Route path="/forecasting" element={<ForecastingPage />} />
          <Route path="/profitability" element={<ProfitabilityPage />} />
          <Route path="/segments" element={<CustomerSegmentsPage />} />
          <Route path="/fx-rates" element={<FxRatesPage />} />
          {phase6 ? <Route path="/governance" element={<EnterpriseGovernancePage />} /> : null}
        </Route>
        <Route path="/" element={<Navigate to="/import" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
