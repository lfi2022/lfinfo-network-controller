import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export const switchKeys = { all: ['switches'] as const, detail: (id: string) => ['switches', id] as const }

export function useSwitches() {
  return useQuery({ queryKey: switchKeys.all, queryFn: api.switches, refetchInterval: 60_000 })
}

export function useSwitchDetail(id: string) {
  return useQuery({ queryKey: switchKeys.detail(id), queryFn: () => api.switchDetail(id), enabled: Boolean(id), refetchInterval: 30_000 })
}
