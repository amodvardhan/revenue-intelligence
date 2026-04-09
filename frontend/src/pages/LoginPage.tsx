import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { LayoutGrid } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { api, setAuthToken } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  tenant_name: z.string().max(200).optional(),
});

type Form = z.infer<typeof schema>;

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const defaultTenantId = import.meta.env.VITE_DEFAULT_TENANT_ID ?? "";
const phase6 = import.meta.env.VITE_ENABLE_PHASE6 === "true";

export function LoginPage() {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const { register, handleSubmit } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", tenant_name: "" },
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const at = params.get("access_token");
    if (!at) return;
    setAuthToken(at);
    void api
      .get<{ email: string }>("/api/v1/auth/me", { headers: { Authorization: `Bearer ${at}` } })
      .then((r) => {
        setSession(at, r.data.email);
        navigate("/import");
        window.history.replaceState({}, "", "/login");
      })
      .catch(() => {
        setAuthToken(null);
      });
  }, [navigate, setSession]);

  const login = useMutation({
    mutationFn: async (data: Form) => {
      const { data: res } = await api.post<{
        access_token: string;
        email: string;
      }>("/api/v1/auth/login", { email: data.email, password: data.password });
      return res;
    },
    onSuccess: (res) => {
      setSession(res.access_token, res.email);
      navigate("/import");
    },
  });

  const registerUser = useMutation({
    mutationFn: async (data: Form) => {
      const { data: res } = await api.post<{
        access_token: string;
        email: string;
      }>("/api/v1/auth/register", {
        email: data.email,
        password: data.password,
        tenant_name: data.tenant_name?.trim() || "My Organization",
      });
      return res;
    },
    onSuccess: (res) => {
      setSession(res.access_token, res.email);
      navigate("/import");
    },
  });

  return (
    <div className="grid min-h-screen md:grid-cols-[minmax(300px,440px)_1fr]">
      <aside className="auth-rail relative hidden flex-col justify-between p-10 lg:p-12 md:flex">
        <div>
          <div className="flex items-center gap-3.5">
            <div className="relative">
              <div className="absolute -inset-1 rounded-2xl bg-primary/40 blur-xl" aria-hidden />
              <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-hover shadow-lg ring-1 ring-white/15">
                <LayoutGrid className="h-7 w-7 text-white" aria-hidden />
              </div>
            </div>
            <div>
              <p className="text-[15px] font-semibold tracking-tight text-white">Revenue Intelligence</p>
              <p className="text-[13px] text-sidebar-muted">Governed revenue analytics</p>
            </div>
          </div>
          <h2 className="mt-14 max-w-[18ch] text-[28px] font-semibold leading-[1.15] tracking-[-0.03em] text-white lg:text-[32px]">
            Clarity for every revenue decision.
          </h2>
          <p className="mt-5 max-w-sm text-[15px] leading-relaxed text-sidebar-muted">
            Import actuals, explore rollups, and ask questions in plain language — with audit trails Finance and IT can
            trust.
          </p>
        </div>
        <p className="text-[12px] text-sidebar-label">Natural language analytics · secure tenant data</p>
      </aside>

      <div className="app-shell-main flex flex-col justify-center px-5 py-12 md:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-[440px]">
          <div className="mb-8 flex items-center gap-3 md:hidden">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-hover shadow-md ring-1 ring-black/10">
              <LayoutGrid className="h-6 w-6 text-white" aria-hidden />
            </div>
            <div>
              <p className="text-[15px] font-semibold text-ink">Revenue Intelligence</p>
              <p className="text-[13px] text-ink-muted">Sign in to continue</p>
            </div>
          </div>

          <header className="mb-8">
            <h1 className="page-headline">Sign in</h1>
            <p className="page-lede mt-2 max-w-md">Use your work email and password. SSO is available when configured.</p>
          </header>

          <div className="surface-card p-8 sm:p-9">
          <form className="space-y-5" onSubmit={handleSubmit((v) => login.mutate(v))}>
            <div>
              <label className="form-field-label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="input-modern h-11 w-full"
                {...register("email")}
              />
            </div>
            <div>
              <label className="form-field-label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input-modern h-11 w-full"
                {...register("password")}
              />
            </div>
            <div>
              <label className="form-field-label" htmlFor="tenant_name">
                Tenant name (register only)
              </label>
              <input id="tenant_name" className="input-modern h-11 w-full" {...register("tenant_name")} />
            </div>
            {(login.error || registerUser.error) && (
              <p className="text-[13px] text-error">Request failed — check credentials or API.</p>
            )}
            {phase6 && defaultTenantId ? (
              <div className="rounded-xl border border-black/[0.06] bg-surface-subtle p-4">
                <p className="mb-3 text-[13px] font-medium text-ink">Enterprise SSO (OIDC)</p>
                <a
                  className="btn-secondary-solid flex w-full px-4"
                  href={`${apiBase}/api/v1/auth/sso/oidc/login?tenant_id=${encodeURIComponent(defaultTenantId)}`}
                >
                  Continue with SSO
                </a>
              </div>
            ) : null}
            <div className="flex flex-col gap-3 pt-1 sm:flex-row">
              <button
                type="submit"
                disabled={login.isPending}
                className="btn-primary-solid flex-1 px-4 disabled:cursor-not-allowed"
              >
                {login.isPending ? "…" : "Continue"}
              </button>
              <button
                type="button"
                disabled={registerUser.isPending}
                className="btn-secondary-solid flex-1 px-4 disabled:cursor-not-allowed"
                onClick={handleSubmit((v) => registerUser.mutate(v))}
              >
                Register
              </button>
            </div>
            <p className="text-center text-[12px] text-neutral-500">
              <Link to="/import" className="font-medium text-primary hover:underline">
                Back to app
              </Link>
            </p>
          </form>
          </div>
        </div>
      </div>
    </div>
  );
}
