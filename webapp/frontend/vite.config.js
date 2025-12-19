import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',  // Zmieniono na 5001 (5000 zajęty przez AirPlay)
        changeOrigin: true
      }
    }
  }
})

