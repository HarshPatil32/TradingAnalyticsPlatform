// Shared helpers and presentational components for the trade report screen
import { AlertCircle, Info, TrendingDown } from 'lucide-react'

export function fmtPct(val, decimals = 1) {
  if (val == null || isNaN(val)) return 'N/A'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${Number(val).toFixed(decimals)}%`
}

export function fmtDate(dateStr) {
  if (!dateStr) return null
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export function computeMetrics(result) {
  const pnl = result.pnl ?? {}
  const trades = result.trades ?? []
  const tradePnl = pnl.trade_pnl ?? []
  const numClosed = tradePnl.length
  const grossReturnPct = pnl.total_return_pct ?? 0
  const grossPnlUsd = pnl.total_pnl ?? 0

  // Back-calculate total capital deployed from gross return %
  const totalCapital =
    grossReturnPct !== 0 ? Math.abs(grossPnlUsd / (grossReturnPct / 100)) : 0

  const commissionsUsd = result.commissions?.total_commission_usd ?? 0
  const slippageUsd = result.slippage?.total_slippage_usd ?? 0
  const spreadUsd = result.bid_ask_spread?.total_spread_usd ?? 0
  // Estimate short-term capital gains tax at 30% of gross profit.
  // Only applied when profit is meaningful (>= $10) to avoid noise on tiny gains.
  const estimatedTaxUsd = grossPnlUsd >= 10 ? Math.max(0, grossPnlUsd * 0.3) : 0

  const netPnlUsd =
    grossPnlUsd - commissionsUsd - slippageUsd - spreadUsd - estimatedTaxUsd
  const netReturnPct = totalCapital > 0 ? (netPnlUsd / totalCapital) * 100 : 0

  // Costs as negative percentages of capital deployed
  const commissionsPct =
    totalCapital > 0 ? -(commissionsUsd / totalCapital) * 100 : 0
  const slippagePct =
    totalCapital > 0 ? -(slippageUsd / totalCapital) * 100 : 0
  const spreadPct =
    totalCapital > 0 ? -(spreadUsd / totalCapital) * 100 : 0
  // Only compute taxPct when there is an actual tax amount to avoid -0
  const taxPct =
    totalCapital > 0 && estimatedTaxUsd > 0 ? -(estimatedTaxUsd / totalCapital) * 100 : 0
  const totalCostPct = commissionsPct + slippagePct + spreadPct + taxPct

  const numWinners = tradePnl.filter((t) => t.pnl > 0).length
  const winRate = numClosed > 0 ? (numWinners / numClosed) * 100 : null

  const spy = result.spy_benchmark ?? null
  const spyReturn = spy?.total_return_pct ?? null
  const qqqReturn = result.qqq_benchmark?.total_return_pct ?? null
  const startDate = spy?.start_date ?? null
  const endDate = spy?.end_date ?? null

  const warnings = result.warnings ?? []
  const dispositionWarning =
    warnings.find((w) => w.type === 'disposition_effect') ?? null
  const overtradingWarning =
    warnings.find((w) => w.type === 'overtrading') ?? null
  const concentrationWarning =
    warnings.find((w) => w.type === 'concentration_risk') ?? null
  const lowSampleWarning =
    warnings.find(
      (w) =>
        w.type === 'insufficient_data' ||
        (w.message && w.message.includes('reliable conclusions'))
    ) ?? null

  const significance = result.significance ?? null

  const avgWinnerDays = pnl.avg_holding_days_winners ?? null
  const avgLoserDays = pnl.avg_holding_days_losers ?? null
  const dispositionRatio =
    avgWinnerDays != null && avgLoserDays != null && avgWinnerDays > 0
      ? avgLoserDays / avgWinnerDays
      : null

  // Notices are info-level items; filter specifically for unclosed positions
  const openCount = (result.notices ?? []).filter(
    (n) => n.type === 'unclosed_position'
  ).length

  return {
    numTrades: trades.length,
    numClosed,
    openCount,
    startDate,
    endDate,
    grossReturnPct,
    netReturnPct,
    commissionsPct,
    slippagePct,
    spreadPct,
    taxPct,
    totalCostPct,
    winRate,
    spyReturn,
    qqqReturn,
    dispositionWarning,
    overtradingWarning,
    concentrationWarning,
    lowSampleWarning,
    avgWinnerDays,
    avgLoserDays,
    dispositionRatio,
    significance,
  }
}

export function StatCard({ label, value, color }) {
  const colorClass =
    color === 'green'
      ? 'text-green-400'
      : color === 'red'
      ? 'text-red-400'
      : 'text-white'
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-zinc-500 uppercase tracking-wide">{label}</span>
      <span className={`text-2xl font-bold ${colorClass}`}>{value}</span>
    </div>
  )
}

export function BenchmarkCard({ label, value, isWinner }) {
  // Guard against future changes to fmtPct's output format by converting to string first
  const valueColor =
    value === 'N/A' || value == null
      ? 'text-zinc-500'
      : String(value).startsWith('+')
      ? 'text-green-400'
      : 'text-red-400'
  return (
    <div className="rounded-xl p-5 flex flex-col gap-2 bg-zinc-800">
      <span className="text-sm text-zinc-400">{label}</span>
      <span className={`text-2xl font-bold ${valueColor}`}>{value}</span>
      {isWinner && (
        <span className="text-xs text-green-400 flex items-center gap-1">
          <TrendingDown className="w-3 h-3 rotate-180" />
          Winner
        </span>
      )}
    </div>
  )
}

export function FlagIcon({ variant }) {
  const configs = {
    error: {
      bg: 'bg-red-500/20',
      icon: <AlertCircle className="w-4 h-4 text-red-400" />,
    },
    warning: {
      bg: 'bg-yellow-500/20',
      icon: <AlertCircle className="w-4 h-4 text-yellow-400" />,
    },
    cost: {
      bg: 'bg-orange-500/20',
      icon: <TrendingDown className="w-4 h-4 text-orange-400" />,
    },
    info: {
      bg: 'bg-zinc-700',
      icon: <Info className="w-4 h-4 text-zinc-400" />,
    },
    success: {
      bg: 'bg-green-500/20',
      icon: <Info className="w-4 h-4 text-green-400" />,
    },
    blue: {
      bg: 'bg-blue-500/20',
      icon: <Info className="w-4 h-4 text-blue-400" />,
    },
  }
  const { bg, icon } = configs[variant] ?? configs.info
  return (
    <div
      className={`w-8 h-8 rounded-full ${bg} flex items-center justify-center flex-shrink-0 mt-0.5`}
    >
      {icon}
    </div>
  )
}

// Cost values arrive as negative percentages from computeMetrics, so fmtPct correctly
// shows them as negative (e.g. "-0.5%"). If the backend ever returns a positive cost
// such as a rebate, fmtPct would show "+x%" with no visual warning — revisit then.
export function CostRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0">
      <span className="text-zinc-400 text-sm">{label}</span>
      <span className="text-red-400 text-sm font-medium">{fmtPct(value)}</span>
    </div>
  )
}
