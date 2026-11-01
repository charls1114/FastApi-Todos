import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 개발 서버에서도 같은 주소로 API 를 호출하도록 백엔드 경로를 모두 넘긴다
    proxy: Object.fromEntries(['/todos', '/auth', '/users', '/friends'].map((path) => [path, 'http://localhost:8000'])),
  },
})
