import { useEffect, useState } from 'react'
import { useSwitches, useSwitchDetail } from '../hooks/useSwitches'
import { DeviceSelect } from '../components/DeviceSelect'
import { Badge, Card } from '../components/ui'
import { Loading, Failure, PortStrip } from './DashboardPage'
import { systemValue, isPortUp } from '../lib/utils'

export function DevicesPage() {
  const switches = useSwitches(); const [id, setId] = useState(''); const selectedId = id || switches.data?.[0]?.id || ''; const detail = useSwitchDetail(selectedId)
  useEffect(() => { const refresh = () => void detail.refetch(); window.addEventListener('lfinfo-refresh', refresh); return () => window.removeEventListener('lfinfo-refresh', refresh) }, [detail])
  if (switches.isLoading || detail.isLoading) return <Loading />
  if (switches.error || detail.error || !detail.data) return <Failure message={(switches.error || detail.error)?.message ?? 'Données indisponibles'} />
  const d = detail.data
  return <><Card className="p-4"><DeviceSelect devices={switches.data ?? []} value={selectedId} onChange={setId} /></Card><Card className="mt-5 p-6"><div className="flex flex-wrap justify-between gap-4"><div><h2 className="text-xl font-bold">{d.name}</h2><p className="mt-1 font-mono text-sm text-slate-500">{d.ip}</p></div><Badge tone="success">● Connecté</Badge></div><PortStrip count={d.ports.length} active={d.ports.filter(isPortUp).map(p => Number(p.port))} /><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Info label="Modèle / matériel" value={systemValue(d, 'hw_version', 'hardware_version', 'model') || d.name} /><Info label="Firmware" value={systemValue(d, 'firmware_version', 'firmware')} /><Info label="Adresse MAC" value={systemValue(d, 'mac', 'mac_address')} /><Info label="Dernière lecture" value={new Intl.DateTimeFormat('fr-BE', { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(d.read_at))} /></div></Card><Card className="mt-5 p-5"><h2 className="font-bold">Informations système brutes</h2><p className="mt-1 text-sm text-slate-500">Champs remontés par le SDK pour cet équipement.</p><dl className="mt-4 grid gap-x-8 sm:grid-cols-2">{Object.entries(d.info).map(([key, value]) => <div key={key} className="flex justify-between gap-4 border-b border-slate-100 py-3 text-sm dark:border-slate-800"><dt className="text-slate-500">{key}</dt><dd className="max-w-[60%] break-words text-right font-medium">{String(value)}</dd></div>)}</dl></Card></>
}
function Info({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 break-all text-sm font-bold">{value}</p></div> }
