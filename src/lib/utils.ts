import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Port, SwitchDetail } from '../types/api'

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))
export const portNumber = (port: Port) => Number(port.port)
export const isPortUp = (port: Port) => Boolean(port.speed_act)

export function pvidFor(device: SwitchDetail, port: number): string | number {
  const pvids = device.pvids
  if (Array.isArray(pvids)) {
    const value = pvids[port - 1]
    if (typeof value === 'number' || typeof value === 'string') return value
    if (value && typeof value === 'object') {
      const data = value as Record<string, unknown>
      return String(data.pvid ?? data.vid ?? data.value ?? '—')
    }
  }
  if (pvids && typeof pvids === 'object') {
    const data = pvids as Record<string, unknown>
    return String(data[port] ?? data[String(port)] ?? '—')
  }
  return '—'
}

export const systemValue = (device: SwitchDetail | undefined, ...keys: string[]) => {
  if (!device) return '—'
  for (const key of keys) {
    const value = device.info[key]
    if (value !== undefined && value !== null && value !== '') return String(value)
  }
  return '—'
}
