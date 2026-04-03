import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom"
import { useEffect } from "react"
import useAuthStore from "@/store/authStore"
import LoginPage from "@/pages/LoginPage"
import RegisterPage from "@/pages/RegisterPage"
import OnboardingPage from "@/pages/OnboardingPage"
import MainPage from "@/pages/MainPage"
import EvolutionLogPage from "@/pages/EvolutionLogPage"
import SettingsPage from "@/pages/SettingsPage"
import ProfilePage from "@/pages/ProfilePage"
import ChatPage from "@/pages/ChatPage"
import DemoChatPage from "@/demo/DemoChatPage"

// API 服务重启后 JWT secret 会变，旧 token 失效
// 此组件挂载时验证 token 有效性，失效则自动登出
function AuthValidator() {
  const { token, user_id, logout } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (!token || !user_id) return
    // 用 GET /user/profile/{user_id} 验证 token，401/403 说明 token 已失效
    fetch(`/user/profile/${user_id}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(res => {
      if (res.status === 401 || res.status === 403) {
        logout()
        navigate("/login", { replace: true })
      }
    }).catch(() => {/* 网络错误不处理 */})
  }, [])

  return null
}

// Route guard: requires auth
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

// Route guard: redirect if already logged in
function RedirectIfAuthed({ children }: { children: React.ReactNode }) {
  const { token, onboarding_done } = useAuthStore()
  if (token) {
    if (onboarding_done) return <Navigate to="/app" replace />
    return <Navigate to="/onboarding" replace />
  }
  return <>{children}</>
}


export default function App() {
  return (
    <BrowserRouter>
      <AuthValidator />
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />

        <Route
          path="/login"
          element={
            <RedirectIfAuthed>
              <LoginPage />
            </RedirectIfAuthed>
          }
        />

        <Route
          path="/register"
          element={
            <RedirectIfAuthed>
              <RegisterPage />
            </RedirectIfAuthed>
          }
        />

        <Route
          path="/onboarding"
          element={
            <RequireAuth>
              <OnboardingPage />
            </RequireAuth>
          }
        />

        <Route
          path="/app"
          element={
            <RequireAuth>
              <MainPage />
            </RequireAuth>
          }
        />

        <Route
          path="/app/log"
          element={
            <RequireAuth>
              <EvolutionLogPage />
            </RequireAuth>
          }
        />

        <Route
          path="/app/settings"
          element={
            <RequireAuth>
              <SettingsPage />
            </RequireAuth>
          }
        />

        <Route
          path="/app/profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />

        <Route
          path="/app/chat"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />

        <Route
          path="/app/demo"
          element={
            <RequireAuth>
              <DemoChatPage />
            </RequireAuth>
          }
        />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
