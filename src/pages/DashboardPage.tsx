import { Activity, Cable, Network, Router } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useEffect } from 'react'
import { useQueries } from '@tanstack/react-query'
import { useSwitches, switchKeys } from '../hooks/useSwitches'
import { api } from '../services/api'
import { isPortUp } from '../lib/utils'
import { Badge, Card } from '../components/ui'

export function DashboardPage() {
  const switches = useSwitches()
  const details = useQueries({ queries: (switches.data ?? []).map(device => ({ queryKey: switchKeys.detail(device.id), queryFn: () => api.switchDetail(device.id), staleTime: 20_000 })) })
  useEffect(() => { const listener = () => void Promise.all([switches.refetch(), ...details.map(detail => detail.refetch())]); window.addEventListener('lfinfo-refresh', listener); return () => window.removeEventListener('lfinfo-refresh', listener) })
  if (switches.isLoading) return <Loading />
  if (switches.error) return <Failure message={switches.error.message} />
  const deviceList = switches.data ?? []; const online = details.filter(q => q.data).length; const ports = details.flatMap(q => q.data?.ports ?? []); const active = ports.filter(isPortUp).length; const vlans = new Set(details.flatMap(q => q.data?.vlans.map(v => v.vid) ?? [])).size
  const stats = [{ label: 'Switches configurés', value: deviceList.length, note: `${online} accessibles`, icon: Router }, { label: 'Ports Ethernet', value: ports.length, note: `${active} liens actifs détectés`, icon: Cable }, { label: 'VLAN détectés', value: vlans, note: 'Identifiants distincts', icon: Network }, { label: 'État du contrôleur', value: `${online}/${deviceList.length}`, note: 'Lectures réussies', icon: Activity }]
  return <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(({ label, value, note, icon: Icon }) => <Card className="p-5" key={label}><div className="flex justify-between text-sm text-slate-500"><span>{label}</span><Icon size={17} className="text-lf" /></div><strong className="mt-3 block text-3xl tracking-tight">{value}</strong><small className="mt-1 block text-slate-400">{note}</small></Card>)}</div>
    <Card className="mt-5 p-5"><div className="mb-5 flex items-center justify-between"><div><h2 className="font-bold">Équipements réseau</h2><p className="mt-1 text-sm text-slate-500">Vos quatre switches TP-Link Easy Smart</p></div><Badge>{deviceList.length} équipements</Badge></div><div className="grid gap-4 lg:grid-cols-2">{deviceList.map((device, index) => <Link to={`/ports?switch=${device.id}`} key={device.id} className="rounded-xl border border-slate-200 p-5 transition hover:border-sky-300 hover:shadow-sm dark:border-slate-700"><div className="flex justify-between gap-3"><div><h3 className="font-bold">{device.name}</h3><p className="mt-1 font-mono text-xs text-slate-500">{device.ip}</p></div><Badge tone={details[index]?.data ? 'success' : details[index]?.isError ? 'danger' : 'neutral'}>{details[index]?.data ? '● En ligne' : details[index]?.isError ? '● Indisponible' : '● Lecture…'}</Badge></div><PortStrip count={device.ports} active={(details[index]?.data?.ports ?? []).filter(isPortUp).map(p => Number(p.port))} /><div className="flex justify-between text-xs text-slate-500"><span>{device.ports} ports Ethernet</span><span>{details[index]?.data?.vlans.length ?? '—'} VLAN →</span></div></Link>)}</div></Card></>
}
export function PortStrip({ count, active }: { count: number; active: number[] }) { return <div className="my-5 flex flex-wrap gap-1.5 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800">{Array.from({ length: count }, (_, i) => <span key={i} className={`grid h-6 w-7 place-items-center rounded text-[10px] font-semibold ${active.includes(i + 1) ? 'bg-emerald-500 text-white' : 'border border-slate-300 bg-slate-200 text-slate-400 dark:border-slate-600 dark:bg-slate-700'}`}>{i + 1}</span>)}</div> }
export function Loading() { return <Card className="p-12 text-center text-slate-500">Chargement des équipements…</Card> }
export function Failure({ message }: { message: string }) { return <Card className="border-rose-200 p-6 text-rose-700">Impossible de contacter l’API : {message}</Card> }
