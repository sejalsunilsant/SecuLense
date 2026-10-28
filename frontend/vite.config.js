import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.SECULENSE_API_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
