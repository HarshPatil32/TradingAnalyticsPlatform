// Full trade analysis report shown after CSV upload
import { AlertCircle, Info, TrendingDown, Crown, ArrowLeft } from 'lucide-react'

function fmtPct(val, decimals = 1) {
  if (val == null || isNaN(val)) return 'N/A'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${Number(val).toFixed(decimals)}%`
}

function fmtDate(dateStr) {
  if (!dateStr) return null
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function computeMetrics(result) {
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
  const taxPct =
    totalCapital > 0 ? -(estimatedTaxUsd / totalCapital) * 100 : 0
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
  const lowSampleWarning =
    warnings.find(
      (w) =>
        w.type === 'insufficient_data' ||
        (w.message && w.message.includes('reliable conclusions'))
    ) ?? null

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
    lowSampleWarning,
    avgWinnerDays,
    avgLoserDays,
    dispositionRatio,
  }
}

function StatCard({ label, value, color }) {
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

function BenchmarkCard({ label, value, isWinner }) {
  return (
    <div className="rounded-xl p-5 flex flex-col gap-2 bg-zinc-800">
      <span className="text-sm text-zinc-400">{label}</span>
      <span
        className={`text-2xl font-bold ${
          value === 'N/A'
            ? 'text-zinc-500'
            : value.startsWith('+')
            ? 'text-green-400'
            : 'text-red-400'
        }`}
      >
        {value}
      </span>
      {isWinner && (
        <span className="text-xs text-green-400 flex items-center gap-1">
          <TrendingDown className="w-3 h-3 rotate-180" />
          Winner
        </span>
      )}
    </div>
  )
}

function FlagIcon({ variant }) {
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

function CostRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0">
      <span className="text-zinc-400 text-sm">{label}</span>
      <span className="text-red-400 text-sm font-medium">{fmtPct(value)}</span>
    </div>
  )
}

export default function TradeReport({ result, onBack }) {
  if (!result) {
    onBack?.()
    return null
  }

  const {
    numTrades, numClosed, openCount, startDate, endDate,
    grossReturnPct, netReturnPct, commissionsPct, slippagePct, spreadPct, taxPct, totalCostPct,
    winRate, spyReturn, qqqReturn,
    dispositionWarning, overtradingWarning, lowSampleWarning,
    avgWinnerDays, avgLoserDays, dispositionRatio,
  } = computeMetrics(result)

  const startLabel = fmtDate(startDate)
  const endLabel = fmtDate(endDate)
  const periodText =
    startLabel && endLabel ? `${startLabel} - ${endLabel}` : 'N/A'

  const spyBeatsStrategy = spyReturn != null && spyReturn > netReturnPct
  const qqqBeatsStrategy = qqqReturn != null && qqqReturn > netReturnPct

  const hasCosts =
    commissionsPct !== 0 ||
    slippagePct !== 0 ||
    spreadPct !== 0 ||
    taxPct !== 0

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white px-4 py-12">
      <div className="max-w-4xl mx-auto">

        {/* Back button */}
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          Upload another file
        </button>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Your Trade Analysis</h1>
          <p className="text-zinc-400">
            Here's the honest breakdown of your trading performance
          </p>
        </div>

        {/* Summary Stats */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-6">
            <StatCard label="Trades Analyzed" value={numTrades} />
            <StatCard label="Period" value={periodText} />
            <StatCard
              label="Gross Return"
              value={fmtPct(grossReturnPct)}
              color={grossReturnPct >= 0 ? 'green' : 'red'}
            />
            <StatCard
              label="After Costs & Tax"
              value={fmtPct(netReturnPct)}
              color={netReturnPct >= 0 ? 'green' : 'red'}
            />
            <StatCard
              label="SPY Same Period"
              value={fmtPct(spyReturn)}
            />
          </div>
        </div>

        {/* Benchmark Comparison */}
        {(spyReturn != null || qqqReturn != null) && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Benchmark Comparison
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <BenchmarkCard
                label="Your Strategy"
                value={fmtPct(netReturnPct)}
              />
              {spyReturn != null && (
                <BenchmarkCard
                  label="SPY (Buy & Hold)"
                  value={fmtPct(spyReturn)}
                  isWinner={spyBeatsStrategy}
                />
              )}
              {qqqReturn != null && (
                <BenchmarkCard
                  label="QQQ (Buy & Hold)"
                  value={fmtPct(qqqReturn)}
                  isWinner={qqqBeatsStrategy}
                />
              )}
            </div>
            {startLabel && endLabel && (
              <p className="text-zinc-500 text-sm mt-4">
                Same date range ({startLabel} - {endLabel}).{' '}
                {spyBeatsStrategy && qqqBeatsStrategy
                  ? 'Both index funds outperformed your active trading strategy.'
                  : spyBeatsStrategy || qqqBeatsStrategy
                  ? 'One or more index funds outperformed your active trading strategy.'
                  : 'Your strategy outperformed the index funds.'}
              </p>
            )}
          </div>
        )}

        {/* Behavioral Flags */}
        <h2 className="text-2xl font-bold text-white mb-4">
          What Your Trades Are Telling You
        </h2>
        <div className="space-y-4 mb-6">

          {/* Disposition effect */}
          {dispositionWarning && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <div className="flex gap-4">
                <FlagIcon variant="error" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white mb-1">
                    {dispositionRatio != null
                      ? `You held losers ${dispositionRatio.toFixed(1)}x longer than winners`
                      : 'You held losing trades longer than winning trades'}
                  </h3>
                  <p className="text-zinc-400 text-sm leading-relaxed">
                    {avgWinnerDays != null && avgLoserDays != null
                      ? `Your winning trades were closed after an average of ${avgWinnerDays} days, while losing trades stayed open for ${avgLoserDays} days. This is a classic sign of the disposition effect — the tendency to sell winners too early and hold onto losers hoping they'll recover.`
                      : dispositionWarning.message}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Trading costs breakdown */}
          {hasCosts && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <div className="flex gap-4">
                <FlagIcon variant="cost" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white mb-1">
                    Trading costs ate {fmtPct(Math.abs(totalCostPct))} of your returns
                  </h3>
                  <p className="text-zinc-400 text-sm mb-4">
                    Your gross return was {fmtPct(grossReturnPct)}, but after accounting for all
                    costs, your net return dropped to {fmtPct(netReturnPct)}. Here's where the
                    money went:
                  </p>
                  <div className="border-t border-zinc-800">
                    <CostRow label="Commissions & Fees" value={commissionsPct} />
                    <CostRow label="Slippage" value={slippagePct} />
                    <CostRow label="Bid-Ask Spread" value={spreadPct} />
                    {taxPct !== 0 && (
                      <CostRow label="Short-term Capital Gains Tax (est.)" value={taxPct} />
                    )}
                    <div className="flex justify-between items-center pt-2">
                      <span className="text-white text-sm font-semibold">Total Impact</span>
                      <span className="text-red-400 text-sm font-semibold">
                        {fmtPct(totalCostPct)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Win rate */}
          {winRate != null && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <div className="flex gap-4">
                <FlagIcon variant="info" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white mb-1">
                    Win rate: {fmtPct(winRate)}
                  </h3>
                  <p className="text-zinc-400 text-sm mb-2">
                    {winRate > 50
                      ? `Just over half your trades were profitable.`
                      : winRate === 50
                      ? `Exactly half your trades were profitable.`
                      : `Under half your trades were profitable.`}{' '}
                    With {numClosed} trades in your sample,{' '}
                    {numClosed < 100
                      ? "this is approaching statistical significance, but you'd need at least 100 trades to confidently say whether this represents a real edge or just luck."
                      : 'this is a statistically meaningful sample size.'}
                  </p>
                  {lowSampleWarning && (
                    <p className="text-zinc-500 text-sm italic">
                      Not enough data yet to call this a proven strategy
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Overtrading */}
          {overtradingWarning && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <div className="flex gap-4">
                <FlagIcon variant="warning" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white mb-1">
                    You're trading more than your edge justifies
                  </h3>
                  <p className="text-zinc-400 text-sm mb-2">
                    {overtradingWarning.message}
                  </p>
                  <p className="text-yellow-400 text-sm font-medium">
                    Consider reducing trade frequency
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Open positions */}
          {openCount > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
              <div className="flex gap-4">
                <FlagIcon variant="blue" />
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-white mb-1">
                    {openCount} open {openCount === 1 ? 'position' : 'positions'}
                  </h3>
                  <p className="text-zinc-400 text-sm">
                    You currently have {openCount}{' '}
                    {openCount === 1 ? 'position' : 'positions'} that{' '}
                    {openCount === 1 ? "hasn't" : "haven't"} been closed yet. These are not
                    included in the performance calculations above. Monitor{' '}
                    {openCount === 1 ? 'this position' : 'these positions'} to avoid the
                    disposition effect.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Upgrade to Pro */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8">
          <div className="flex items-center gap-2 mb-2">
            <Crown className="w-5 h-5 text-yellow-400" />
            <h2 className="text-xl font-bold text-white">Upgrade to Pro</h2>
          </div>
          <p className="text-zinc-400 text-sm mb-6">
            Get the complete picture of your trading behavior and unlock deeper insights
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {[
              {
                title: 'Full behavioral breakdown',
                desc: 'Detailed analysis of all cognitive biases affecting your trades',
              },
              {
                title: 'Per-stock performance',
                desc: 'See which tickers you actually make money on vs. which ones lose',
              },
              {
                title: 'Monthly trend tracking',
                desc: "Track whether you're improving over time or repeating mistakes",
              },
              {
                title: 'Custom alerts',
                desc: "Get notified when you're falling into bad trading patterns",
              },
            ].map(({ title, desc }) => (
              <div key={title}>
                <p className="text-white text-sm font-semibold mb-0.5">{title}</p>
                <p className="text-zinc-400 text-sm">{desc}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="px-6 py-3 bg-white text-black font-semibold rounded-xl hover:bg-zinc-100 transition-colors text-sm">
              Upgrade Now
            </button>
            <button className="px-6 py-3 bg-zinc-800 text-white font-semibold rounded-xl hover:bg-zinc-700 transition-colors text-sm border border-zinc-700">
              Save These Results (Free)
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
