import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../services/api'

function sessionId() { return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}` }

export function useLiveTraffic(switchId: string, enabled: boolean) {
  const [clientId] = useState(sessionId)
  const query = useQuery({ queryKey: ['live-traffic', switchId, clientId], queryFn: () => api.liveTraffic(switchId, clientId), enabled: enabled && Boolean(switchId), refetchInterval: enabled ? 2_000 : false, refetchIntervalInBackground: false, staleTime: 0 })
  return query
}
