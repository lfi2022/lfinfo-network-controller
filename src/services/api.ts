import type { AuditEntry, ControllerStatus, LiveTrafficResponse, NewSwitchInput, StatisticsPeriod, StatisticsResponse, SwitchDetail, SwitchInput, SwitchSummary } from '../types/api'

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
  createSwitch: (input: NewSwitchInput) => request<SwitchSummary>('/switches', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }),
  updateSwitch: (id: string, input: Omit<SwitchInput, 'password'> & { password?: string }) => request<SwitchSummary>(`/switches/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) }),
  deleteSwitch: (id: string) => request<void>(`/switches/${id}`, { method: 'DELETE' }),
  testSwitch: (id: string) => request<{ ok: boolean; switch: SwitchDetail }>(`/switches/${id}/test`, { method: 'POST' }),
  importLegacy: () => request<{ added: string[]; skipped: { ip: string; reason: string }[] }>('/switches/import-legacy', { method: 'POST' }),
  audit: () => request<AuditEntry[]>('/audit'),
  statistics: (period: StatisticsPeriod, switchId?: string) => request<StatisticsResponse>(`/statistics?period=${period}${switchId ? `&switch_id=${encodeURIComponent(switchId)}` : ''}`),
  liveTraffic: (id: string, clientId: string) => request<LiveTrafficResponse>(`/live/switches/${id}?client_id=${encodeURIComponent(clientId)}`),
  setPortEnabled: (id: string, port: number, enabled: boolean) => request<SwitchDetail>(`/switches/${id}/ports/${port}/enabled`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, confirm: true }),
  }),
  setPvid: (id: string, port: number, pvid: number) => request<SwitchDetail>(`/switches/${id}/ports/${port}/pvid`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pvid, confirm: true }),
  }),
}
