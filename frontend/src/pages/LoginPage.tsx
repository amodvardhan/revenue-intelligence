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
  tenant_name: z.string().min(1).optional(),
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
    defaultValues: { email: "", password: "" },
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
        tenant_name: data.tenant_name ?? "My Organization",
      });
      return res;
    },
    onSuccess: (res) => {
      setSession(res.access_token, res.email);
      navigate("/import");
    },
  });

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <h1 className="text-display mb-6 text-3xl font-semibold text-slate-900">Sign in</h1>
      <form
        className="space-y-4 rounded-lg border border-border bg-white p-6 shadow-sm"
        onSubmit={handleSubmit((v) => login.mutate(v))}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            className="h-10 w-full rounded-md border border-border px-3 text-sm"
            {...register("email")}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className="h-10 w-full rounded-md border border-border px-3 text-sm"
            {...register("password")}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="tenant_name">
            Tenant name (register only)
          </label>
          <input
            id="tenant_name"
            className="h-10 w-full rounded-md border border-border px-3 text-sm"
            {...register("tenant_name")}
          />
        </div>
        {(login.error || registerUser.error) && (
          <p className="text-sm text-error">Request failed — check credentials or API.</p>
        )}
        {phase6 && defaultTenantId ? (
          <div className="rounded-md border border-border bg-slate-50 p-3">
            <p className="mb-2 text-xs text-slate-600">Enterprise SSO (OIDC)</p>
            <a
              className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-white"
              href={`${apiBase}/api/v1/auth/sso/oidc/login?tenant_id=${encodeURIComponent(defaultTenantId)}`}
            >
              Continue with SSO
            </a>
          </div>
        ) : null}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={login.isPending}
            className="h-10 flex-1 rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
          >
            {login.isPending ? "…" : "Login"}
          </button>
          <button
            type="button"
            disabled={registerUser.isPending}
            className="h-10 flex-1 rounded-md border border-border bg-white px-4 text-sm font-medium text-slate-800"
            onClick={handleSubmit((v) => registerUser.mutate(v))}
          >
            Register
          </button>
        </div>
        <p className="text-center text-xs text-slate-500">
          <Link to="/import" className="text-primary">
            Back to app
          </Link>
        </p>
      </form>
    </div>
  );
}
