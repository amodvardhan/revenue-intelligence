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
  Sparkles,
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
  `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${
    isActive
      ? "bg-white/10 text-white shadow-inner shadow-black/20 ring-1 ring-white/10"
      : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
  }`;

export function AppSidebar() {
  const email = useAuthStore((s) => s.email);
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();

  return (
    <aside className="relative flex h-screen w-[260px] shrink-0 flex-col border-r border-white/5 bg-slate-950 shadow-[4px_0_24px_rgba(0,0,0,0.12)]">
      <div
        className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-teal-400/40 via-cyan-500/20 to-transparent"
        aria-hidden
      />
      <div className="border-b border-white/5 px-5 pb-5 pt-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-cyan-600 shadow-glow">
            <Sparkles className="h-5 w-5 text-white" aria-hidden />
          </div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight text-white">Revenue Intelligence</div>
            <div className="mt-0.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
              Natural-language analytics
            </div>
          </div>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 py-4" aria-label="Primary">
        <NavLink to="/import" className={linkClass} end>
          <FileSpreadsheet className="h-4 w-4 shrink-0 opacity-80 group-hover:opacity-100" aria-hidden />
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
      <div className="border-t border-white/5 p-4">
        {email ? (
          <div className="mb-3 truncate rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-400" title={email}>
            {email}
          </div>
        ) : null}
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-medium text-slate-400 transition-colors hover:bg-white/5 hover:text-slate-100 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/50"
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
