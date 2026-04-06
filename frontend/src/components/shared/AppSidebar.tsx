import {
  BarChart3,
  ClipboardList,
  Coins,
  FileSpreadsheet,
  Link2,
  LogOut,
  MessageSquareText,
  Percent,
  Shield,
  Table,
  TrendingUp,
  Users,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";

import { useAuthStore } from "@/store/authStore";

const phase5 = import.meta.env.VITE_ENABLE_PHASE5 === "true";
const phase6 = import.meta.env.VITE_ENABLE_PHASE6 === "true";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary ${
    isActive
      ? "border-l-4 border-primary bg-primary-muted text-primary"
      : "text-slate-600 hover:bg-slate-100"
  }`;

export function AppSidebar() {
  const email = useAuthStore((s) => s.email);
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-border bg-surface-elevated shadow-sm">
      <div className="border-b border-border px-4 py-4">
        <div className="text-lg font-semibold text-slate-900">Revenue Intelligence</div>
        <div className="mt-1 text-xs text-slate-500">Revenue intelligence</div>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Primary">
        <NavLink to="/import" className={linkClass} end>
          <FileSpreadsheet className="h-4 w-4" aria-hidden />
          Import
        </NavLink>
        <NavLink to="/revenue" className={linkClass}>
          <Table className="h-4 w-4" aria-hidden />
          Revenue
        </NavLink>
        <NavLink to="/analytics" className={linkClass}>
          <BarChart3 className="h-4 w-4" aria-hidden />
          Analytics
        </NavLink>
        <NavLink to="/ask" className={linkClass}>
          <MessageSquareText className="h-4 w-4" aria-hidden />
          Ask
        </NavLink>
        <NavLink to="/query-audit" className={linkClass}>
          <ClipboardList className="h-4 w-4" aria-hidden />
          Query audit
        </NavLink>
        <NavLink to="/integrations/hubspot" className={linkClass}>
          <Link2 className="h-4 w-4" aria-hidden />
          HubSpot
        </NavLink>
        {phase6 ? (
          <NavLink to="/governance" className={linkClass}>
            <Shield className="h-4 w-4" aria-hidden />
            Governance
          </NavLink>
        ) : null}
        {phase5 ? (
          <>
            <NavLink to="/forecasting" className={linkClass}>
              <TrendingUp className="h-4 w-4" aria-hidden />
              Forecasting
            </NavLink>
            <NavLink to="/profitability" className={linkClass}>
              <Percent className="h-4 w-4" aria-hidden />
              Profitability
            </NavLink>
            <NavLink to="/segments" className={linkClass}>
              <Users className="h-4 w-4" aria-hidden />
              Segments
            </NavLink>
            <NavLink to="/fx-rates" className={linkClass}>
              <Coins className="h-4 w-4" aria-hidden />
              FX rates
            </NavLink>
          </>
        ) : null}
      </nav>
      <div className="border-t border-border p-3">
        {email ? (
          <div className="mb-2 truncate text-xs text-slate-500" title={email}>
            {email}
          </div>
        ) : null}
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary"
          onClick={() => {
            queryClient.clear();
            clear();
          }}
        >
          <LogOut className="h-4 w-4 shrink-0" aria-hidden />
          Log out
        </button>
      </div>
    </aside>
  );
}
