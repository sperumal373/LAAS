import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    target: 'esnext',
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // React + ReactDOM → tiny, long-cached vendor chunk
          if (id.includes('node_modules')) {
            return 'vendor';
          }
          // OpenShift page is lazy-loaded — already its own dynamic chunk,
          // but naming it explicitly keeps it stable across builds.
          if (id.includes('OpenShiftPage')) {
            return 'openshift';
          }
          if (id.includes('NutanixPage')) {
            return 'nutanix';
          }
          // API helpers in their own cacheable chunk
          if (id.includes('/src/api')) {
            return 'api';
          }
          // Everything else → main app chunk
        },
      },
    },
  },
})
