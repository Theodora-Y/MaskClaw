import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getAccentColor, getGradient, DEFAULT_ACCENT, DEFAULT_GRADIENT } from '@/lib/colorMap'

interface AuthState {
  user_id: string | null
  token: string | null
  username: string | null
  occupation: string | null
  apps: string[]
  sensitive_fields: string[]
  onboarding_done: boolean
  accentColor: string
  gradFrom: string
  gradTo: string
  avatarIndex: number

  setAuth: (
    user_id: string,
    token: string,
    username: string,
    onboarding_done: boolean
  ) => void
  setProfile: (
    occupation: string,
    apps: string[],
    sensitive_fields: string[]
  ) => void
  setAccentColor: (color: string) => void
  setGradient: (from: string, to: string) => void
  setAvatarIndex: (index: number) => void
  logout: () => void
}

const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user_id: null,
      token: null,
      username: null,
      occupation: null,
      apps: [],
      sensitive_fields: [],
      onboarding_done: false,
      accentColor: DEFAULT_ACCENT,
      gradFrom: DEFAULT_GRADIENT.from,
      gradTo: DEFAULT_GRADIENT.to,
      avatarIndex: 0,

      setAuth: (user_id, token, username, onboarding_done) =>
        set({
          user_id,
          token,
          username,
          onboarding_done,
          gradFrom: DEFAULT_GRADIENT.from,
          gradTo: DEFAULT_GRADIENT.to,
        }),

      setProfile: (occupation, apps, sensitive_fields) => {
        const gradient = getGradient(occupation)
        set({
          occupation,
          apps,
          sensitive_fields,
          accentColor: getAccentColor(occupation),
          gradFrom: gradient.from,
          gradTo: gradient.to,
        })
      },

      setAccentColor: (color) => set({ accentColor: color }),

      setGradient: (from, to) => set({ gradFrom: from, gradTo: to }),

      setAvatarIndex: (index) => set({ avatarIndex: index }),

      logout: () =>
        set({
          user_id: null,
          token: null,
          username: null,
          occupation: null,
          apps: [],
          sensitive_fields: [],
          onboarding_done: false,
          accentColor: DEFAULT_ACCENT,
          gradFrom: DEFAULT_GRADIENT.from,
          gradTo: DEFAULT_GRADIENT.to,
          avatarIndex: 0,
        }),
    }),
    {
      name: 'maskclaw-auth',
      partialize: (state) => ({
        user_id: state.user_id,
        token: state.token,
        username: state.username,
        occupation: state.occupation,
        apps: state.apps,
        sensitive_fields: state.sensitive_fields,
        onboarding_done: state.onboarding_done,
        accentColor: state.accentColor,
        gradFrom: state.gradFrom,
        gradTo: state.gradTo,
        avatarIndex: state.avatarIndex,
      }),
    }
  )
)

export default useAuthStore
