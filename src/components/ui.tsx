import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../lib/utils'

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn('rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900', className)}>{children}</section>
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'success' | 'danger' | 'info' }) {
  const colors = { neutral: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300', success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300', danger: 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300', info: 'bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300' }
  return <span className={cn('inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold', colors[tone])}>{children}</span>
}

export function Button({ className, variant = 'primary', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' }) {
  const colors = { primary: 'bg-lf text-white hover:bg-[#075a9a]', secondary: 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800', danger: 'bg-rose-600 text-white hover:bg-rose-700' }
  return <button className={cn('inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50', colors[variant], className)} {...props} />
}
