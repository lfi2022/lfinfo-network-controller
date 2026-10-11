import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { DeviceSelect } from '../components/DeviceSelect'
import { Card } from '../components/ui'
import { useSwitchDetail, useSwitches } from '../hooks/useSwitches'
import { Loading, Failure } from './DashboardPage'
import { isPortUp } from '../lib/utils'

export function InsightsPage() {
  const switches = useSwitches(); const [id, setId] = useState(''); const selected = id || switches.data?.[0]?.id || ''; const detail = useSwitchDetail(selected)
  if (switches.isLoading || detail.isLoading) return <Loading />
  if (switches.error || detail.error || !detail.data) return <Failure message={(switches.error || detail.error)?.message ?? 'Données indisponibles'} />
  const data = detail.data.ports.map(port => ({ port: `P${port.port}`, link: isPortUp(port) ? 1 : 0 }))
  return <><Card className="p-4"><DeviceSelect devices={switches.data ?? []} value={selected} onChange={setId} /></Card><div className="mt-5 grid gap-5 lg:grid-cols-2"><Card className="p-5"><h2 className="font-bold">Liens détectés</h2><p className="mt-1 text-sm text-slate-500">État en temps réel, issu de la lecture des ports.</p><div className="mt-5 h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="port" /><YAxis allowDecimals={false} domain={[0, 1]} /><Tooltip /><Bar dataKey="link" name="Lien actif" fill="#096DB9" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Card><Card className="p-5"><h2 className="font-bold">TX / RX et erreurs</h2><p className="mt-3 text-sm leading-6 text-slate-500">Le SDK utilisé par le backend actuel ne fournit pas encore de compteurs uniformes TX, RX ou erreurs pour les quatre firmwares. Cette zone reste volontairement informative pour éviter de présenter des données simulées.</p><div className="mt-6 rounded-lg bg-slate-50 p-4 text-sm dark:bg-slate-800"><b>Statut :</b> fonctionnalité non disponible dans l’API actuelle.</div></Card></div></>
}
