import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: 'static',
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8502',
        changeOrigin: true,
        // Disable buffering for SSE streaming
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // Ensure streaming requests are not buffered
            req.socket.setNoDelay(true);
          });
        },
      },
    },
  },
});
