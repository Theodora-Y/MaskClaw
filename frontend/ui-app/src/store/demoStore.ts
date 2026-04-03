import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type DemoUserKey = 'UserA' | 'UserB' | 'UserC'

interface DemoState {
  isDemoMode: boolean
  demoUser: DemoUserKey
  setDemoMode: (v: boolean) => void
  setDemoUser: (u: DemoUserKey) => void
}

const useDemoStore = create<DemoState>()(
  persist(
    (set) => ({
      isDemoMode: false,
      demoUser: 'UserC',
      setDemoMode: (v) => set({ isDemoMode: v }),
      setDemoUser: (u) => set({ demoUser: u }),
    }),
    { name: 'maskclaw-demo' }
  )
)

export default useDemoStore
