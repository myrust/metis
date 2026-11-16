interface RadialGaugeProps {
  label: string
  value: number
  subtitle?: string
  color?: string
}

export function RadialGauge({
  label,
  value,
  subtitle,
  color = '#10b981',
}: RadialGaugeProps) {
  const clamped = Math.max(0, Math.min(100, value))
  const radius = 30
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (clamped / 100) * circumference

  const strokeColor =
    clamped >= 90 ? '#f43f5e' : clamped >= 75 ? '#f59e0b' : color

  return (
    <div className="flex flex-col items-center justify-center gap-1.5">
      <div className="relative flex h-20 w-20 items-center justify-center">
        <svg className="h-20 w-20 -rotate-90" viewBox="0 0 76 76">
          <circle
            cx="38"
            cy="38"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeOpacity="0.12"
            strokeWidth="7"
          />
          <circle
            cx="38"
            cy="38"
            r={radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-500"
          />
        </svg>
        <span className="absolute text-sm font-semibold">{clamped.toFixed(0)}%</span>
      </div>
      <div className="text-xs font-medium">{label}</div>
      {subtitle && <div className="text-[10px] opacity-60">{subtitle}</div>}
    </div>
  )
}

interface CustomChartSvgProps {
  chartType: string
  labels: string[]
  values: number[]
}

export function CustomChartSvg({ chartType, labels, values }: CustomChartSvgProps) {
  const max = Math.max(...values, 1)

  if (chartType === 'ring') {
    const total = values.reduce((a, b) => a + b, 0) || 1
    const pct = Math.round(((values[0] ?? 0) / total) * 100)
    return (
      <div className="flex items-center justify-around py-2">
        <RadialGauge label={labels[0] ?? 'Primary'} value={pct} color="#6366f1" />
        <div className="space-y-1 text-xs">
          {labels.map((l, i) => (
            <div key={`${l}-${i}`} className="flex items-center justify-between gap-4">
              <span className="opacity-70">{l}</span>
              <span className="font-mono font-semibold">{values[i] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (chartType === 'line') {
    const w = 260
    const h = 90
    const pts = values
      .map((v, i) => {
        const x = values.length <= 1 ? w / 2 : (i / (values.length - 1)) * (w - 20) + 10
        const y = h - 12 - (v / max) * (h - 24)
        return `${x},${y}`
      })
      .join(' ')
    return (
      <div>
        <svg viewBox={`0 0 ${w} ${h}`} className="h-24 w-full">
          <polyline
            fill="none"
            stroke="#10b981"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={pts}
          />
          {values.map((v, i) => {
            const x = values.length <= 1 ? w / 2 : (i / (values.length - 1)) * (w - 20) + 10
            const y = h - 12 - (v / max) * (h - 24)
            return <circle key={i} cx={x} cy={y} r="3.5" fill="#10b981" />
          })}
        </svg>
        <div className="flex justify-between text-[10px] opacity-60">
          {labels.map((l, i) => (
            <span key={i}>{l}</span>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-28 items-end gap-2 pt-3">
      {values.map((v, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-[10px] font-mono opacity-70">{v}</span>
          <div className="flex h-16 w-full items-end rounded-xl bg-zinc-500/10 p-1">
            <div
              className="w-full rounded-lg bg-emerald-400/85 transition-all"
              style={{ height: `${Math.max(8, (v / max) * 100)}%` }}
            />
          </div>
          <span className="truncate text-[10px] opacity-65">{labels[i] ?? ''}</span>
        </div>
      ))}
    </div>
  )
}

interface FluxTokenPanelProps {
  totalTokens: number
  totalCostUsd: number
  forecast30dUsd: number
  successRate: number
  daily: Array<{ day: string; tokens: number; cost_usd: number; calls: number }>
  innerSurface: string
}

export function FluxTokenPanel({
  totalTokens,
  totalCostUsd,
  forecast30dUsd,
  successRate,
  daily,
  innerSurface,
}: FluxTokenPanelProps) {
  const ticks = daily.length > 0 ? daily : Array.from({ length: 14 }, (_, i) => ({
    day: `D${i + 1}`,
    tokens: (i % 5) + 1,
    cost_usd: 0,
    calls: i % 3,
  }))
  const maxTok = Math.max(...ticks.map((d) => d.tokens), 1)
  const budgetCap = Math.max(forecast30dUsd * 1.5, 1.0)
  const usedPct = Math.min(60, Math.round((totalCostUsd / budgetCap) * 100))
  const reservedPct = Math.min(40, Math.round((forecast30dUsd / budgetCap) * 100))
  const unusedPct = Math.max(10, 100 - usedPct - reservedPct)

  const formatTok = (n: number) =>
    n >= 1_000_000 ? `${(n / 1_000_000).toFixed(2)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}K` : `${n}`

  return (
    <div className="space-y-3">
      {/* 3 Flux-style KPI Cards with vertical tick sparklines */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
          <div className="text-[11px] opacity-60">Token (7d)</div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xl font-semibold">{formatTok(totalTokens)}</span>
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
              Live
            </span>
          </div>
          <div className="mt-3 flex h-8 items-end gap-1">
            {ticks.map((d, idx) => (
              <span
                key={idx}
                title={`${d.day}: ${d.tokens} tok`}
                className="flex-1 rounded-full bg-emerald-500/75"
                style={{ height: `${Math.max(18, (d.tokens / maxTok) * 100)}%` }}
              />
            ))}
          </div>
        </div>

        <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
          <div className="text-[11px] opacity-60">Cost (7d)</div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xl font-semibold">${totalCostUsd.toFixed(4)}</span>
          </div>
          <div className="mt-3 flex h-8 items-end gap-1">
            {ticks.map((d, idx) => (
              <span
                key={idx}
                className="flex-1 rounded-full bg-indigo-500/70"
                style={{ height: `${Math.max(18, ((d.calls + 1) / 5) * 100)}%` }}
              />
            ))}
          </div>
        </div>

        <div className={`rounded-2xl border p-3.5 ${innerSurface}`}>
          <div className="text-[11px] opacity-60">Success Rate</div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-xl font-semibold">{successRate.toFixed(1)}%</span>
          </div>
          <div className="mt-3 flex h-8 items-end gap-1">
            {ticks.map((_, idx) => (
              <span
                key={idx}
                className={`flex-1 rounded-full ${
                  idx % 7 === 5 ? 'bg-amber-400/80' : 'bg-emerald-500/75'
                }`}
                style={{ height: `${idx % 7 === 5 ? 55 : 90}%` }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* 30-day Cost Forecast segmented bar (Flux style) */}
      <div className={`rounded-2xl border p-4 ${innerSurface}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs opacity-60">30-day Cost Forecast</div>
            <div className="mt-0.5 text-2xl font-semibold">${forecast30dUsd.toFixed(4)}</div>
          </div>
          <div className="flex items-center gap-3 text-[11px] opacity-75">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-sky-400" /> Unused {unusedPct}%
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-amber-500" /> Used {usedPct}%
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500" /> Projected {reservedPct}%
            </span>
          </div>
        </div>
        <div className="mt-3 flex h-5 w-full items-center gap-1 overflow-hidden rounded-xl">
          <div
            className="h-full rounded-lg bg-sky-400/75"
            style={{ width: `${unusedPct}%` }}
          />
          <div
            className="h-full rounded-lg bg-amber-500/85"
            style={{ width: `${Math.max(6, usedPct)}%` }}
          />
          <div
            className="h-full rounded-lg bg-emerald-500/80"
            style={{ width: `${Math.max(8, reservedPct)}%` }}
          />
        </div>
      </div>
    </div>
  )
}
