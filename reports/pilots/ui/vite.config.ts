/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The API serves the build from /ui/ under a strict CSP (script-src 'self', style-src 'self'):
// no inline scripts, no data: assets, no inline style attributes in components.
export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  build: { outDir: 'dist', modulePreload: { polyfill: false }, assetsInlineLimit: 0, sourcemap: false },
  server: { proxy: { '/api': 'http://localhost:8081' } },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
});
