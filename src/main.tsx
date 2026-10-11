import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { PortsPage } from './pages/PortsPage'
import { VlansPage } from './pages/VlansPage'
import { InsightsPage } from './pages/InsightsPage'
import { StatisticsPage } from './pages/StatisticsPage'
import { SettingsPage } from './pages/SettingsPage'
import './styles.css'

const router = createBrowserRouter([{ element: <AppLayout />, children: [
  { path: '/', element: <DashboardPage /> }, { path: '/devices', element: <DevicesPage /> }, { path: '/ports', element: <PortsPage /> }, { path: '/vlans', element: <VlansPage /> }, { path: '/statistics', element: <StatisticsPage /> }, { path: '/insights', element: <InsightsPage /> }, { path: '/settings', element: <SettingsPage /> },
] }], { basename: '/' })
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })
createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider></StrictMode>)
