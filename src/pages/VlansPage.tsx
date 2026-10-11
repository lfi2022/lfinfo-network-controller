import { useState } from 'react'
import { DeviceSelect } from '../components/DeviceSelect'
import { Badge, Card } from '../components/ui'
import { useSwitchDetail, useSwitches } from '../hooks/useSwitches'
import { Loading, Failure } from './DashboardPage'

export function VlansPage() {
  const switches = useSwitches(); const [id, setId] = useState(''); const selected = id || switches.data?.[0]?.id || ''; const detail = useSwitchDetail(selected)
  if (switches.isLoading || detail.isLoading) return <Loading />
  if (switches.error || detail.error || !detail.data) return <Failure message={(switches.error || detail.error)?.message ?? 'Données indisponibles'} />
  const d = detail.data
  return <><Card className="p-4"><div className="flex flex-wrap items-center gap-3"><DeviceSelect devices={switches.data ?? []} value={selected} onChange={setId} /><Badge tone={d.vlans_enabled ? 'success' : 'neutral'}>{d.vlans_enabled ? '802.1Q activé' : '802.1Q non signalé'}</Badge></div></Card><Card className="mt-5 p-5"><h2 className="font-bold">Matrice VLAN · {d.name}</h2><p className="mt-1 text-sm text-slate-500">Lecture seule. Les modifications de membership VLAN ne sont pas exposées par le backend actuel.</p><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[680px] border-collapse text-center text-sm"><thead><tr><th className="sticky left-0 bg-white p-3 text-left dark:bg-slate-900">VLAN</th>{d.ports.map(p => <th className="p-3 text-slate-500" key={String(p.port)}>P{p.port}</th>)}</tr></thead><tbody>{d.vlans.map(vlan => <tr className="border-t border-slate-100 dark:border-slate-800" key={String(vlan.vid)}><td className="sticky left-0 bg-white p-3 text-left dark:bg-slate-900"><b>{vlan.vid}</b><span className="ml-2 text-xs text-slate-500">{vlan.name || 'Sans nom'}</span></td>{d.ports.map(port => { const n = Number(port.port); const state = vlan.untagged_ports?.includes(n) ? 'U' : vlan.tagged_ports?.includes(n) ? 'T' : '—'; return <td className="p-3" key={n}><span className={state === 'U' ? 'rounded bg-slate-200 px-2 py-1 text-xs font-bold text-slate-700 dark:bg-slate-700 dark:text-slate-100' : state === 'T' ? 'rounded bg-sky-100 px-2 py-1 text-xs font-bold text-lf dark:bg-sky-950' : 'text-slate-300'}>{state}</span></td> })}</tr>)}</tbody></table></div><div className="mt-4 flex gap-5 text-xs text-slate-500"><span><b className="mr-1 text-lf">T</b> Tagged</span><span><b className="mr-1">U</b> Untagged</span><span>— Excluded</span></div></Card></>
}
