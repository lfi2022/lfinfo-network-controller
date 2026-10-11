import type { ControllerStatus, SwitchDetail, SwitchSummary } from '../types/api'

export class ApiError extends Error {
  constructor(message: string, public status?: number) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { cache: 'no-store', ...init })
  const payload: unknown = await response.json().catch(() => undefined)
  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'detail' in payload
      ? String(payload.detail) : `Erreur HTTP ${response.status}`
    throw new ApiError(message, response.status)
  }
  return payload as T
}

export const api = {
  controllerStatus: () => request<ControllerStatus>('/controller/status'),
  switches: () => request<SwitchSummary[]>('/switches'),
  switchDetail: (id: string) => request<SwitchDetail>(`/switches/${id}`),
  setPortEnabled: (id: string, port: number, enabled: boolean) => request<SwitchDetail>(`/switches/${id}/ports/${port}/enabled`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, confirm: true }),
  }),
  setPvid: (id: string, port: number, pvid: number) => request<SwitchDetail>(`/switches/${id}/ports/${port}/pvid`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pvid, confirm: true }),
  }),
}
