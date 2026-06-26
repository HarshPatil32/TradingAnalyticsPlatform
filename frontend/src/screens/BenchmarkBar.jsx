// Side-by-side bar chart comparing user return vs SPY and QQQ
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'

function barColor(value) {
  if (value == null) return '#52525b'
  return value >= 0 ? '#4ade80' : '#f87171'
}

export function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const name = payload[0].payload.name
  const value = payload[0].value
  if (value == null) return null
  const sign = value >= 0 ? '+' : ''
  return (
    <div className="bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white">
      {name}: {sign}{value.toFixed(1)}%
    </div>
  )
}

export default function BenchmarkBar({ userReturn, spyReturn, qqqReturn }) {
  const data = [
    { name: 'Your Strategy', value: userReturn },
    spyReturn != null ? { name: 'SPY', value: spyReturn } : null,
    qqqReturn != null ? { name: 'QQQ', value: qqqReturn } : null,
  ].filter(Boolean)

  if (data.length < 2) return null

  const allValues = data.map((d) => d.value)
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const padding = Math.max(Math.abs(max - min) * 0.3, 5)
  const domain = [Math.floor(min - padding), Math.ceil(max + padding)]

  return (
    <div className="mt-6">
      <p className="text-sm text-zinc-400 mb-3">Return Comparison</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: '#a1a1aa', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: '#a1a1aa', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            domain={domain}
            width={50}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 4" />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={80}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={barColor(entry.value)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
