import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({mode}) => {
  const env=loadEnv(mode,'.','TRACKER_');
  const target=env.TRACKER_API_TARGET || 'http://localhost:8080';
  return {
    plugins: [react()],
    server: { proxy: { '/api': target, '/actuator': target } },
  };
});
