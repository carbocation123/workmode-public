import { fileURLToPath, URL } from 'node:url'

export default {
  resolve: {
    alias: {
      react: fileURLToPath(new URL('../frontend/node_modules/react', import.meta.url)),
      'react-dom': fileURLToPath(new URL('../frontend/node_modules/react-dom', import.meta.url)),
      'react-markdown': fileURLToPath(new URL('../frontend/node_modules/react-markdown', import.meta.url)),
      'remark-gfm': fileURLToPath(new URL('../frontend/node_modules/remark-gfm', import.meta.url)),
    },
  },
}
