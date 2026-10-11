import { BarChart3, Boxes, Cable, ChartNoAxesCombined, LayoutDashboard, Moon, RefreshCw, Settings, Sun, Tags } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { cn } from '../lib/utils'
import { Button } from './ui'

const links = [
  { to: '/', label: 'Tableau de bord', icon: LayoutDashboard, end: true },
  { to: '/devices', label: 'Équipements', icon: Boxes },
  { to: '/ports', label: 'Ports', icon: Cable },
  { to: '/vlans', label: 'VLAN', icon: Tags },
  { to: '/statistics', label: 'Statistiques', icon: ChartNoAxesCombined },
  { to: '/insights', label: 'Insights', icon: BarChart3 },
]

const names: Record<string, [string, string]> = {
  '/': ['Vue d’ensemble', 'Supervision centralisée des switches TP-Link Easy Smart.'],
  '/devices': ['Équipements', 'Inventaire et informations des switches gérés.'],
  '/ports': ['Ports', 'État et configuration réseau par port.'],
  '/vlans': ['Réseaux virtuels', 'Lecture 802.1Q et matrice des appartenances.'],
  '/insights': ['Insights', 'Indicateurs disponibles via le switch.'],
  '/statistics': ['Statistiques', 'Analyse historique des paquets réseau.'],
  '/settings': ['Paramètres', 'Configuration et sécurité du contrôleur.'],
}

export function AppLayout() {
  const location = useLocation()
  const [dark, setDark] = useState(() => localStorage.getItem('lf-theme') === 'dark')
  useEffect(() => { document.documentElement.classList.toggle('dark', dark); localStorage.setItem('lf-theme', dark ? 'dark' : 'light') }, [dark])
  const [title, subtitle] = names[location.pathname] ?? names['/']
  return <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-[#101721] dark:text-slate-100">
    <aside className="fixed inset-y-0 left-0 z-20 flex w-[68px] flex-col items-center border-r border-slate-200 bg-white py-4 dark:border-slate-700 dark:bg-slate-900">
      <img className="h-10 w-10 rounded-xl border border-slate-200 object-contain p-1 dark:border-slate-700" src="/static/lfinfo-logo.webp" alt="LFINFO" />
      <nav className="mt-7 flex flex-1 flex-col gap-2" aria-label="Navigation principale">
        {links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} title={label} className={({ isActive }) => cn('grid h-11 w-11 place-items-center rounded-xl text-slate-400 transition hover:bg-sky-50 hover:text-lf dark:hover:bg-slate-800', isActive && 'bg-sky-50 text-lf dark:bg-sky-950')}><Icon size={21} /><span className="sr-only">{label}</span></NavLink>)}
      </nav>
      <NavLink to="/settings" title="Paramètres" className={({ isActive }) => cn('grid h-11 w-11 place-items-center rounded-xl text-slate-400 transition hover:bg-sky-50 hover:text-lf dark:hover:bg-slate-800', isActive && 'bg-sky-50 text-lf dark:bg-sky-950')}><Settings size={21} /><span className="sr-only">Paramètres</span></NavLink>
    </aside>
    <div className="ml-[68px] flex min-h-screen flex-col">
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-5 sm:px-8 dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-baseline gap-2"><strong className="tracking-widest">LFINFO</strong><span className="font-semibold text-lf">Network</span><span className="hidden text-xs text-slate-400 sm:inline">Switch Controller</span></div>
        <div className="flex items-center gap-3"><span className="hidden text-xs text-emerald-600 sm:inline">● API sécurisée</span><Button variant="secondary" className="!p-2" onClick={() => setDark(value => !value)} aria-label="Changer de thème">{dark ? <Sun size={18} /> : <Moon size={18} />}</Button><span className="grid h-8 w-8 place-items-center rounded-full bg-slate-800 text-[10px] font-bold text-white">LF</span></div>
      </header>
      <main className="mx-auto w-full max-w-[1580px] flex-1 px-4 py-7 sm:px-8">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="text-[10px] font-bold tracking-[.14em] text-slate-400">GESTION RÉSEAU / <span className="text-lf">{title.toUpperCase()}</span></p><h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1><p className="mt-1 text-sm text-slate-500">{subtitle}</p></div><RefreshAction /></div>
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 px-5 py-4 text-xs text-slate-400 dark:border-slate-700">LFINFO Network Controller · Administration locale · Écritures verrouillées par défaut</footer>
    </div>
  </div>
}

function RefreshAction() {
  return <Button variant="secondary" onClick={() => window.dispatchEvent(new Event('lfinfo-refresh'))}><RefreshCw size={16} />Actualiser</Button>
}
