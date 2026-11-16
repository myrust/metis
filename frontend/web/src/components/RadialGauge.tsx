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
