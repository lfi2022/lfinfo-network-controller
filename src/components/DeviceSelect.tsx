import type { SwitchSummary } from '../types/api'

export function DeviceSelect({ devices, value, onChange }: { devices: SwitchSummary[]; value: string; onChange: (id: string) => void }) {
  return <select aria-label="Sélectionner un switch" value={value} onChange={event => onChange(event.target.value)} className="min-w-56 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm shadow-sm outline-none ring-lf focus:ring-2 dark:border-slate-700 dark:bg-slate-900">
    {devices.map(device => <option key={device.id} value={device.id}>{device.name} · {device.ip}</option>)}
  </select>
}
