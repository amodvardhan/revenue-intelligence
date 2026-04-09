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

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13px] font-medium transition-colors duration-150 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-[#F5F5F7] ${
    isActive
      ? "bg-white text-neutral-900 shadow-sm"
      : "text-neutral-600 hover:bg-black/[0.04] hover:text-neutral-900"
  }`;

const iconClass = "h-[18px] w-[18px] shrink-0 opacity-90";

export function AppSidebar() {
  const email = useAuthStore((s) => s.email);
  const clear = useAuthStore((s) => s.clear);
  const queryClient = useQueryClient();

  return (
    <aside className="flex h-screen w-[240px] shrink-0 flex-col border-r border-black/[0.06] bg-[#F5F5F7]">
      <div className="px-4 pb-4 pt-7">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-neutral-900">
            <LayoutGrid className="h-[18px] w-[18px] text-white" aria-hidden />
          </div>
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold leading-tight tracking-tight text-neutral-900">
              Revenue Intelligence
            </div>
            <div className="mt-0.5 text-[11px] leading-snug text-neutral-500">Natural language analytics</div>
          </div>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 pb-4" aria-label="Primary">
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
        <NavLink to="/delivery-managers" className={linkClass}>
          <Contact className={iconClass} aria-hidden />
          Delivery managers
        </NavLink>
        <NavLink to="/team/users" className={linkClass}>
          <UserPlus className={iconClass} aria-hidden />
          Team users
        </NavLink>
        <NavLink to="/projects" className={linkClass}>
          <FolderKanban className={iconClass} aria-hidden />
          Projects
        </NavLink>
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
        {phase5 ? (
          <>
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
          </>
        ) : null}
      </nav>
      <div className="border-t border-black/[0.06] p-3">
        {email ? (
          <div
            className="mb-2 truncate rounded-[10px] border border-black/[0.06] bg-white px-3 py-2 text-[11px] text-neutral-600"
            title={email}
          >
            {email}
          </div>
        ) : null}
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-[10px] px-3 py-2.5 text-left text-[13px] font-medium text-neutral-600 transition-colors hover:bg-black/[0.04] hover:text-neutral-900 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/35"
          onClick={() => {
            queryClient.clear();
            clear();
          }}
        >
          <LogOut className="h-[18px] w-[18px] shrink-0" aria-hidden />
          Log out
        </button>
      </div>
    </aside>
  );
}
