/// <reference types="vite/client" />

declare namespace ImportMetaEnv {
  interface Env {
    readonly VITE_API_URL: string;
  }
}

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
