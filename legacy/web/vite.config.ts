import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In dev, proxy API and stored media to the Go server so the frontend can use
// same-origin relative URLs (no CORS). In prod, set VITE_API_BASE at build time.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/storage': 'http://localhost:8080',
    },
  },
})
