import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/worldsmith/',
  server: {
    port: 5173,
    proxy: {
      '/world': 'http://localhost:8000',
      '/characters': 'http://localhost:8000',
    },
  },
})
