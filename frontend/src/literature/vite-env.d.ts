interface ImportMetaEnv {
  readonly VITE_WORKMODE_API_BASE?: string
  readonly VITE_LITERATURE_PROJECT_SLUG?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
