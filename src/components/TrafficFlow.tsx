import { motion, useReducedMotion } from 'motion/react'

export function TrafficFlow({ rx, tx, active, stale = false, compact = false }: { rx: number | null | undefined; tx: number | null | undefined; active: boolean; stale?: boolean; compact?: boolean }) {
  const reduced = useReducedMotion(); const rxValue = rx ?? 0; const txValue = tx ?? 0; const total = rxValue + txValue
  const strength = Math.min(1, Math.log1p(total) / Math.log(501))
  const particles = total > 0 && active && !stale && !reduced ? Math.max(1, Math.min(4, Math.ceil(strength * 4))) : 0
  const duration = Math.max(.55, 3.4 - strength * 2.6)
  return <div className={`traffic-flow ${compact ? 'w-12' : 'w-full'} ${stale ? 'opacity-45' : ''}`} aria-label={stale ? 'Mesure périmée' : `RX ${format(rxValue)} et TX ${format(txValue)} paquets par seconde`}>
    <svg viewBox="0 0 120 28" className="h-7 w-full overflow-visible" role="img"><path d="M4 9H116" className="stroke-sky-300 dark:stroke-sky-800" strokeWidth="1.5" /><path d="M116 19H4" className="stroke-emerald-300 dark:stroke-emerald-800" strokeWidth="1.5" />
      {Array.from({ length: particles }, (_, index) => <motion.circle key={`rx-${index}`} cx="4" cy="9" r="2" fill="#096DB9" initial={{ cx: 4, opacity: .2 }} animate={{ cx: 116, opacity: [0, 1, 1, 0] }} transition={{ duration, repeat: Infinity, delay: index * duration / particles, ease: 'linear' }} />)}
      {Array.from({ length: particles }, (_, index) => <motion.circle key={`tx-${index}`} cx="116" cy="19" r="2" fill="#34c28a" initial={{ cx: 116, opacity: .2 }} animate={{ cx: 4, opacity: [0, 1, 1, 0] }} transition={{ duration: duration * 1.08, repeat: Infinity, delay: index * duration / particles, ease: 'linear' }} />)}
    </svg>
    {!compact && <div className="flex justify-between text-[10px] font-medium"><span className="text-lf">↓ {format(rxValue)} p/s</span><span className="text-emerald-600">↑ {format(txValue)} p/s</span><span className="text-slate-500">Σ {format(total)}</span></div>}
    {stale && <p className="text-[10px] text-amber-600">Mesure en attente</p>}
  </div>
}
function format(value: number) { return new Intl.NumberFormat('fr-BE', { maximumFractionDigits: value < 10 ? 2 : 0 }).format(value) }
