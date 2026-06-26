// Equity curve chart: cumulative P&L over time across closed trades
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

export default function EquityCurve({ equityCurve }) {
  if (!equityCurve || equityCurve.length < 2) return null

  const lastPnl = equityCurve[equityCurve.length - 1].cumulative_pnl
  const lineColor = lastPnl >= 0 ? '#4ade80' : '#f87171'

  const data = equityCurve.map((p) => ({ date: p.date, pnl: p.cumulative_pnl }))

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-1">P&L Over Time</h2>
      <p className="text-zinc-400 text-sm mb-4">
        Cumulative profit/loss across closed trades
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis
            dataKey="date"
            tick={{ fill: '#71717a', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#71717a', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            width={55}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: 8,
            }}
            labelStyle={{ color: '#a1a1aa', fontSize: 12 }}
            formatter={(val) => [`$${Number(val).toFixed(2)}`, 'Cumulative P&L']}
          />
          <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="3 3" />
          <Line
            type="monotone"
            dataKey="pnl"
            stroke={lineColor}
            dot={false}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
