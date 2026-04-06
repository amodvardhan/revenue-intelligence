import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
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
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_20%_0%,rgba(45,212,191,0.25),transparent),radial-gradient(ellipse_60%_50%_at_100%_30%,rgba(56,189,248,0.12),transparent)]"
        aria-hidden
      />
      <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col lg:flex-row">
        <div className="flex flex-1 flex-col justify-center px-8 py-14 lg:max-w-md lg:py-20 lg:pr-4">
          <div className="mb-10 text-white">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300/90">Revenue Intelligence</p>
            <h1 className="text-display mt-3 text-4xl font-bold tracking-tight text-white lg:text-[2.75rem]">
              Ask revenue in plain language.
            </h1>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
              Sign in to explore imports, analytics, and governed natural-language queries — built for leaders who need
              answers without waiting on a queue.
            </p>
          </div>
          <form
            className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.07] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur-xl"
            onSubmit={handleSubmit((v) => login.mutate(v))}
          >
            <h2 className="text-lg font-semibold text-white">Sign in</h2>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="h-11 w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 text-sm text-white placeholder:text-slate-500 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/30"
                {...register("email")}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="h-11 w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 text-sm text-white placeholder:text-slate-500 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/30"
                {...register("password")}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-slate-400" htmlFor="tenant_name">
                Tenant name (register only)
              </label>
              <input
                id="tenant_name"
                className="h-11 w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 text-sm text-white placeholder:text-slate-500 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/30"
                {...register("tenant_name")}
              />
            </div>
            {(login.error || registerUser.error) && (
              <p className="text-sm text-red-300">Request failed — check credentials or API.</p>
            )}
            {phase6 && defaultTenantId ? (
              <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                <p className="mb-3 text-xs font-medium text-slate-300">Enterprise SSO (OIDC)</p>
                <a
                  className="inline-flex h-10 w-full items-center justify-center rounded-xl bg-white px-3 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
                  href={`${apiBase}/api/v1/auth/sso/oidc/login?tenant_id=${encodeURIComponent(defaultTenantId)}`}
                >
                  Continue with SSO
                </a>
              </div>
            ) : null}
            <div className="flex gap-3 pt-1">
              <button
                type="submit"
                disabled={login.isPending}
                className="h-11 flex-1 rounded-xl bg-gradient-to-r from-primary to-teal-500 px-4 text-sm font-semibold text-white shadow-lg shadow-teal-900/40 transition hover:brightness-110 disabled:opacity-50"
              >
                {login.isPending ? "…" : "Login"}
              </button>
              <button
                type="button"
                disabled={registerUser.isPending}
                className="h-11 flex-1 rounded-xl border border-white/15 bg-transparent px-4 text-sm font-semibold text-white transition hover:bg-white/10"
                onClick={handleSubmit((v) => registerUser.mutate(v))}
              >
                Register
              </button>
            </div>
            <p className="text-center text-xs text-slate-500">
              <Link to="/import" className="font-medium text-teal-300/90 hover:text-teal-200">
                Back to app
              </Link>
            </p>
          </form>
        </div>
        <div className="relative hidden flex-1 lg:flex lg:items-stretch">
          <div className="m-8 flex flex-1 flex-col justify-between rounded-3xl border border-white/10 bg-gradient-to-br from-teal-900/40 via-slate-900/60 to-slate-950 p-10">
            <div className="space-y-6">
              <div className="inline-flex rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-teal-200/90">
                Executive-ready
              </div>
              <blockquote className="text-xl font-medium leading-snug text-white/95">
                “What we needed wasn’t more dashboards — it was a direct line from question to number, with traceability.”
              </blockquote>
            </div>
            <div className="mt-12 grid grid-cols-3 gap-4 border-t border-white/10 pt-8">
              {[
                { k: "Rollups", v: "Org → BU → Division" },
                { k: "Compare", v: "MoM · QoQ · YoY" },
                { k: "Ask", v: "Governed NL → SQL" },
              ].map((item) => (
                <div key={item.k}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{item.k}</p>
                  <p className="mt-1 text-sm text-slate-200">{item.v}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
