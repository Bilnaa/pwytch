interface ImportMetaEnv {
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// hls.js ships no types for its light build, it has the same API as the full one
declare module 'hls.js/light' {
  export { default } from 'hls.js'
}
