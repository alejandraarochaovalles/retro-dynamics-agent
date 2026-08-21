/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of apps/api. Defaults to http://127.0.0.1:8000 when unset. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
