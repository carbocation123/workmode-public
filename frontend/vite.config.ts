import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    rollupOptions: {
      input: {
        main: 'index.html',
        literature: 'literature/index.html',
        transcription: 'transcription/index.html'
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173
  }
})
