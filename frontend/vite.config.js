import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  preview: {
    // Stessa porta del dev server, cosi' nginx non va toccato
    port: 3000,
    host: '0.0.0.0',
    strictPort: true,
  },
})
