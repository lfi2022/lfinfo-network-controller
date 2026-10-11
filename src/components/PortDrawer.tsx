import * as Dialog from '@radix-ui/react-dialog'
import * as AlertDialog from '@radix-ui/react-alert-dialog'
import { Radio, X } from 'lucide-react'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { isPortUp, portNumber, pvidFor } from '../lib/utils'
import { switchKeys } from '../hooks/useSwitches'
import type { LivePortSample, Port, SwitchDetail } from '../types/api'
import { TrafficFlow } from './TrafficFlow'
import { Badge, Button } from './ui'

type Props = {
  device: SwitchDetail; port: Port | undefined; writesEnabled: boolean; open: boolean
  onOpenChange: (open: boolean) => void; live: boolean; onLiveChange: (enabled: boolean) => void
  sample?: LivePortSample; stale: boolean; age: number | null; interval: number
}

export function PortDrawer({ device, port, writesEnabled, open, onOpenChange, live, onLiveChange, sample, stale, age, interval }: Props) {
  const client = useQueryClient(); const [pvid, setPvid] = useState(''); const [pending, setPending] = useState<'pvid' | 'enabled' | null>(null)
  const mutation = useMutation({ mutationFn: async () => {
    if (!port || !pending) return device
    const n = portNumber(port)
    return pending === 'pvid' ? api.setPvid(device.id, n, Number(pvid)) : api.setPortEnabled(device.id, n, !port.enabled)
  }, onSuccess: data => { client.setQueryData(switchKeys.detail(device.id), data); onOpenChange(false) } })
  if (!port) return null
  const n = portNumber(port); const tagged = device.vlans.filter(v => v.tagged_ports?.includes(n)).map(v => v.vid).join(', ') || '—'; const untagged = device.vlans.filter(v => v.untagged_ports?.includes(n)).map(v => v.vid).join(', ') || '—'
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="port-overlay fixed inset-0 z-30 bg-slate-950/40" /><Dialog.Content className="port-drawer fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-auto bg-white p-6 shadow-2xl dark:bg-slate-900">
    <div className="flex items-start justify-between"><div><p className="text-xs font-bold tracking-wider text-lf">{device.name} / PORT {n}</p><Dialog.Title className="mt-1 text-2xl font-bold">Port {n}</Dialog.Title></div><Dialog.Close asChild><Button variant="secondary" className="!p-2" aria-label="Fermer"><X size={18} /></Button></Dialog.Close></div>
    <div className="mt-5"><Badge tone={isPortUp(port) ? 'success' : 'neutral'}>{isPortUp(port) ? '● Lien actif' : port.enabled ? '● Activé · sans lien' : '● Désactivé'}</Badge></div>
    <section className="mt-5 rounded-xl border border-sky-100 bg-sky-50/60 p-4 dark:border-sky-950 dark:bg-slate-800/80"><div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">Live Traffic</h2><p className="mt-0.5 text-xs text-slate-500">RX/TX mesurés en paquets par seconde</p></div><Button variant={live ? 'primary' : 'secondary'} className="!px-3 !py-2" onClick={() => onLiveChange(!live)}><Radio size={15} />{live ? 'Live actif' : 'Activer Live'}</Button></div>{live ? <div className="mt-3"><TrafficFlow rx={sample?.rx_pps} tx={sample?.tx_pps} active={Boolean(sample?.active)} stale={stale} /><p className="mt-2 text-xs text-slate-500">Collecte matérielle toutes les {interval}s{age === null ? ' · en attente du relevé' : ` · dernier relevé il y a ${age}s`}</p></div> : <p className="mt-3 text-xs leading-5 text-slate-500">Activez Live pour suivre les mesures déjà collectées par le serveur. Aucune configuration réseau n’est modifiée.</p>}</section>
    <dl className="mt-5 divide-y divide-slate-200 text-sm dark:divide-slate-700"><Row label="Vitesse négociée" value={port.speed_act || 'Non disponible'} /><Row label="Vitesse configurée" value={port.speed_cfg || '—'} /><Row label="Duplex" value={port.duplex || '—'} /><Row label="PVID" value={pvidFor(device, n)} /><Row label="VLAN tagged" value={tagged} /><Row label="VLAN untagged" value={untagged} /></dl>
    <div className="mt-6"><label className="mb-2 block text-sm font-medium">Modifier le PVID</label><select value={pvid || String(pvidFor(device, n))} onChange={e => setPvid(e.target.value)} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-800">{device.vlans.map(v => <option key={String(v.vid)} value={String(v.vid)}>{v.vid} · {v.name || 'Sans nom'}</option>)}</select></div>
    <div className="mt-4 flex flex-wrap gap-2"><ConfirmAction label="Appliquer le PVID" disabled={!writesEnabled || !pvid} onConfirm={() => { setPending('pvid'); setTimeout(() => mutation.mutate(), 0) }} /><ConfirmAction label={port.enabled ? 'Désactiver le port' : 'Activer le port'} disabled={!writesEnabled} danger={Boolean(port.enabled)} onConfirm={() => { setPending('enabled'); setTimeout(() => mutation.mutate(), 0) }} /></div>
    {mutation.error && <p className="mt-3 text-sm text-rose-600">{mutation.error.message}</p>}<p className="mt-5 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-800 dark:bg-amber-950/50 dark:text-amber-200">Les écritures exigent l’activation serveur et une confirmation. Vérifiez l’uplink, le VLAN d’administration et les trunks avant toute modification.</p>
  </Dialog.Content></Dialog.Portal></Dialog.Root>
}
function Row({ label, value }: { label: string; value: string | number | boolean | null | undefined }) { return <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">{label}</dt><dd className="text-right font-semibold">{String(value ?? '—')}</dd></div> }
function ConfirmAction({ label, disabled, danger, onConfirm }: { label: string; disabled: boolean; danger?: boolean; onConfirm: () => void }) { return <AlertDialog.Root><AlertDialog.Trigger asChild><Button variant={danger ? 'danger' : 'primary'} disabled={disabled}>{label}</Button></AlertDialog.Trigger><AlertDialog.Portal><AlertDialog.Overlay className="fixed inset-0 z-50 bg-slate-950/50" /><AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"><AlertDialog.Title className="text-lg font-bold">Confirmer la modification réseau</AlertDialog.Title><AlertDialog.Description className="mt-2 text-sm text-slate-500">Cette commande peut interrompre la connectivité. Elle sera enregistrée par le switch seulement après cette confirmation.</AlertDialog.Description><div className="mt-5 flex justify-end gap-2"><AlertDialog.Cancel asChild><Button variant="secondary">Annuler</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>Confirmer</Button></AlertDialog.Action></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root> }
