export interface SwitchSummary { id: string; name: string; ip: string; ports: number }

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
