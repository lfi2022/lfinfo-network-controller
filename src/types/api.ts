export interface SwitchSummary {
  id: string; name: string; ip: string; ports: number; model?: string; firmware?: string | null
  enabled?: boolean; last_status?: string; last_tested_at?: string | null
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
export interface AuditEntry { id: number; occurred_at: string; actor: string; action: string; switch_id: number | null; details: string }
