import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/auth': 'http://localhost:8001',
      '/user': 'http://localhost:8001',
      '/evolution': 'http://localhost:8001',
      '/skills': 'http://localhost:8001',
      '/console': 'http://localhost:8001',
      '/notifications': 'http://localhost:8001',
      '/task': 'http://localhost:8001',
      '/logs': 'http://localhost:8001',
      // AutoGLM Windows 后端（通过 SSH 隧道转发）
      '/autoglm': {
        target: 'http://127.0.0.1:28080',
        changeOrigin: true,
        // SSE 流特殊配置：关闭缓冲
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('X-Accel-Buffering', 'no')
          })
          proxy.on('proxyRes', (proxyRes) => {
            // 确保不缓冲 SSE 响应
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        },
      },
    },
  },
})
