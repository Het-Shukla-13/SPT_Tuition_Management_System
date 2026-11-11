/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Google Sign-In OAuth client id (public). Empty = no Google button. */
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
