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
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#F5F5F7] px-5 py-12">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-900 shadow-sm">
            <LayoutGrid className="h-6 w-6 text-white" aria-hidden />
          </div>
          <h1 className="page-headline">Revenue Intelligence</h1>
          <p className="page-lede">Sign in with your work email to open imports, analytics, and Ask.</p>
        </div>

        <div className="rounded-2xl border border-black/[0.06] bg-white p-8 shadow-card">
          <form className="space-y-5" onSubmit={handleSubmit((v) => login.mutate(v))}>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-neutral-800" htmlFor="email">
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
              <label className="mb-1.5 block text-[13px] font-medium text-neutral-800" htmlFor="password">
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
              <label className="mb-1.5 block text-[13px] font-medium text-neutral-800" htmlFor="tenant_name">
                Tenant name (register only)
              </label>
              <input id="tenant_name" className="input-modern h-11 w-full" {...register("tenant_name")} />
            </div>
            {(login.error || registerUser.error) && (
              <p className="text-[13px] text-red-600">Request failed — check credentials or API.</p>
            )}
            {phase6 && defaultTenantId ? (
              <div className="rounded-[10px] border border-black/[0.06] bg-surface-subtle p-4">
                <p className="mb-3 text-[12px] font-medium text-neutral-700">Enterprise SSO (OIDC)</p>
                <a
                  className="flex h-11 w-full items-center justify-center rounded-[10px] border border-black/[0.1] bg-white text-[15px] font-medium text-neutral-900 shadow-sm transition hover:bg-neutral-50"
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
                className="btn-primary-solid h-11 flex-1 px-4 disabled:cursor-not-allowed"
              >
                {login.isPending ? "…" : "Continue"}
              </button>
              <button
                type="button"
                disabled={registerUser.isPending}
                className="flex h-11 flex-1 items-center justify-center rounded-[10px] border border-black/[0.12] bg-white px-4 text-[15px] font-medium text-neutral-900 transition hover:bg-neutral-50 disabled:opacity-50"
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
  );
}
