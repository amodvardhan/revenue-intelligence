/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** When "true", show Phase 5 nav and call Phase 5 APIs (requires ENABLE_PHASE5 on backend). */
  readonly VITE_ENABLE_PHASE5?: string;
  /** Phase 6 — Enterprise SSO & governance UI (requires ENABLE_SSO / migrated schema on backend). */
  readonly VITE_ENABLE_PHASE6?: string;
  /** When "true", show Phase 7 matrix and delivery-manager APIs (requires ENABLE_PHASE7 on backend). */
  readonly VITE_ENABLE_PHASE7?: string;
  /** Default tenant UUID for the "Continue with SSO" link on the login page. */
  readonly VITE_DEFAULT_TENANT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
