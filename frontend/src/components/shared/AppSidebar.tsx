import type { ReactNode } from "react";
import {
  BarChart3,
  ClipboardList,
  Building2,
  Contact,
  Coins,
  FolderKanban,
  UserPlus,
  FileSpreadsheet,
  LayoutGrid,
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
const phase7 = import.meta.env.VITE_ENABLE_PHASE7 === "true";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `group flex min-h-[44px] items-center gap-3 rounded-xl border-l-[3px] py-2 pl-[13px] pr-3 text-[13px] font-medium transition-all duration-200 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar ${
    isActive
      ? "border-primary bg-white/[0.09] text-sidebar-ink shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]"
      : "border-transparent text-sidebar-muted hover:bg-white/[0.05] hover:text-sidebar-ink"
  }`;

const iconClass = "app-sidebar-icon h-[18px] w-[18px] shrink-0";

function NavSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="pt-3 first:pt-0">
      <p className="mb-1.5 px-3 text-[12px] font-medium text-sidebar-label">{label}</p>
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}

export function AppSidebar() {
  const email = useAuthStore((s) => s.email);
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();

  return (
    <aside className="flex h-full min-h-0 w-[272px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar shadow-nav">
      <div className="shrink-0 px-4 pb-5 pt-8">
        <div className="flex items-center gap-3.5">
          <div className="relative">
            <div className="absolute -inset-1 rounded-2xl bg-primary/35 blur-lg" aria-hidden />
            <div className="relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-hover shadow-lg ring-1 ring-white/10">
              <LayoutGrid className="h-[19px] w-[19px] text-white" aria-hidden />
            </div>
          </div>
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold leading-tight tracking-[-0.02em] text-sidebar-ink">
              Revenue Intelligence
            </div>
            <div className="mt-0.5 text-[12px] leading-snug text-sidebar-muted">Natural language analytics</div>
          </div>
        </div>
      </div>
      <nav className="app-sidebar-nav flex flex-1 flex-col gap-0 overflow-y-auto overflow-x-hidden px-3 pb-4" aria-label="Primary">
        <NavSection label="Workspace">
          <NavLink to="/import" className={linkClass} end>
            <FileSpreadsheet className={iconClass} aria-hidden />
            Import
          </NavLink>
          <NavLink to="/revenue" className={linkClass}>
            <Table className={iconClass} aria-hidden />
            Revenue
          </NavLink>
          <NavLink to="/customers" className={linkClass}>
            <Building2 className={iconClass} aria-hidden />
            Customers
          </NavLink>
          {phase7 ? (
            <NavLink to="/delivery-managers" className={linkClass}>
              <Contact className={iconClass} aria-hidden />
              Delivery managers
            </NavLink>
          ) : null}
          <NavLink to="/team/users" className={linkClass}>
            <UserPlus className={iconClass} aria-hidden />
            Team users
          </NavLink>
          <NavLink to="/projects" className={linkClass}>
            <FolderKanban className={iconClass} aria-hidden />
            Projects
          </NavLink>
        </NavSection>

        <NavSection label="Insights">
          <NavLink to="/analytics" className={linkClass}>
            <BarChart3 className={iconClass} aria-hidden />
            Analytics
          </NavLink>
          <NavLink to="/ask" className={linkClass}>
            <MessageSquareText className={iconClass} aria-hidden />
            Ask
          </NavLink>
          <NavLink to="/query-audit" className={linkClass}>
            <ClipboardList className={iconClass} aria-hidden />
            Query audit
          </NavLink>
        </NavSection>

        <NavSection label="Platform">
          <NavLink to="/integrations/hubspot" className={linkClass}>
            <Link2 className={iconClass} aria-hidden />
            HubSpot
          </NavLink>
          {phase6 ? (
            <NavLink to="/governance" className={linkClass}>
              <Shield className={iconClass} aria-hidden />
              Governance
            </NavLink>
          ) : null}
        </NavSection>

        {phase5 ? (
          <NavSection label="Financial planning">
            <NavLink to="/forecasting" className={linkClass}>
              <TrendingUp className={iconClass} aria-hidden />
              Forecasting
            </NavLink>
            <NavLink to="/profitability" className={linkClass}>
              <Percent className={iconClass} aria-hidden />
              Profitability
            </NavLink>
            <NavLink to="/segments" className={linkClass}>
              <Users className={iconClass} aria-hidden />
              Segments
            </NavLink>
            <NavLink to="/fx-rates" className={linkClass}>
              <Coins className={iconClass} aria-hidden />
              FX rates
            </NavLink>
          </NavSection>
        ) : null}
      </nav>
      <div className="shrink-0 border-t border-sidebar-border bg-sidebar-elevated/90 p-3 backdrop-blur-md">
        {email ? (
          <div
            className="mb-2 truncate rounded-xl border border-white/[0.08] bg-white/[0.06] px-3 py-2.5 text-[12px] text-sidebar-muted"
            title={email}
          >
            {email}
          </div>
        ) : null}
        <button
          type="button"
          className="flex min-h-[44px] w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-[13px] font-medium text-sidebar-muted transition-colors duration-200 hover:bg-white/[0.06] hover:text-sidebar-ink focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/45 focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar"
          onClick={() => {
            queryClient.clear();
            clear();
          }}
        >
          <LogOut className="h-[18px] w-[18px] shrink-0 opacity-90" aria-hidden />
          Log out
        </button>
      </div>
    </aside>
  );
}
