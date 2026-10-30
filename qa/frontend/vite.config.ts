import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5175, proxy: { '/api': 'http://127.0.0.1:8090' } },
  test: { environment: 'jsdom', restoreMocks: true, unstubGlobals: true },
});
