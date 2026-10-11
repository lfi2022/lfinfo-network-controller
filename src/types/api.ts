export interface SwitchSummary {
  id: string; name: string; ip: string; ports: number; model?: string; firmware?: string | null
  enabled?: boolean; last_status?: string; last_tested_at?: string | null
  last_error?: string | null
}

export interface Port {
  port: number | string
  enabled?: boolean
  speed_act?: string | null
  speed_cfg?: string | null
  duplex?: string | null
  flow_control?: boolean | string | null
  [key: string]: unknown
}

export interface Vlan {
  vid: number | string
  name?: string
  tagged_ports?: number[]
  untagged_ports?: number[]
  [key: string]: unknown
}

export interface SwitchDetail {
  id: string
  name: string
  ip: string
  info: Record<string, unknown>
  ports: Port[]
  vlans_enabled: boolean
  vlans: Vlan[]
  pvids: unknown
  read_at: string
}

export interface ControllerStatus { writes_enabled: boolean }
export interface SwitchInput { name: string; ip: string; model: string; firmware?: string; ports: number; password: string; enabled: boolean }
export interface NewSwitchInput { ip: string; password: string }
export interface AuditEntry { id: number; occurred_at: string; actor: string; action: string; switch_id: number | null; details: string }
export type StatisticsPeriod = '15m' | '1h' | '6h' | '24h'
export interface PortSample { recorded_at: string; switch_id: number; port: number; tx_pps: number | null; rx_pps: number | null; active: number; speed_mbps: number | null; speed_cfg: string }
export interface VlanSample { recorded_at: string; switch_id: number; vlan_count: number | null }
export interface CollectionStatus { switch_id: number; collected_at: string | null; last_error: string | null }
export interface StatisticsResponse { period: StatisticsPeriod; start: string; samples: PortSample[]; vlan_samples: VlanSample[]; collection: CollectionStatus[]; retention_days: number; interval_seconds: number }
export interface LivePortSample { recorded_at: string; port: number; tx_pps: number | null; rx_pps: number | null; active: number; speed_mbps: number | null; speed_cfg: string }
export interface LiveTrafficResponse { switch_id: string; samples: LivePortSample[]; collection_interval_seconds: number; client_expires_at: string; collected_at: string | null; last_error: string | null }
