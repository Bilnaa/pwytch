import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { Layout } from '@/components/layout'
import { RequireAuth } from '@/components/require-auth'
import { AuthProvider } from '@/lib/auth'
import { GoLivePage } from '@/pages/go-live'
import { HomePage } from '@/pages/home'
import { LoginPage } from '@/pages/login'
import { RegisterPage } from '@/pages/register'
import { SearchPage } from '@/pages/search'
import { VideoPage } from '@/pages/video'
import { NotFoundPage } from '@/pages/not-found'
import './index.css'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/search', element: <SearchPage /> },
      { path: '/videos/:id', element: <VideoPage /> },
      {
        // channel of a streamer, like twitch. The fixed paths above (/login...) win over it
        path: '/:username',
        // the player (vidstack + hls.js) is heavy, it's only loaded when someone opens a channel
        lazy: async () => ({ Component: (await import('@/pages/channel')).ChannelPage }),
      },
      {
        element: <RequireAuth />,
        children: [{ path: '/go-live', element: <GoLivePage /> }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </StrictMode>,
)
