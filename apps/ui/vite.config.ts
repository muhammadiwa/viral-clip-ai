
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }: { mode: string }) => {
  // Load environment variables
  const env = loadEnv(mode, process.cwd(), '')

  const devApiHost = env.DEV_API_HOST || 'api'
  const devApiPort = env.DEV_API_PORT || '8000'
  const devUiHost = env.DEV_UI_HOST || '0.0.0.0'
  const devUiPort = parseInt(env.DEV_UI_PORT || '5173')

  return {
    plugins: [react()],
    server: {
      port: devUiPort,
      host: devUiHost,
      proxy: {
        '/api': {
          target: `http://${devApiHost}:${devApiPort}`,
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api/, '')
        }
      }
    }
  }
})
