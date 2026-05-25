// Full trade analysis report shown after CSV upload
import { Crown, ArrowLeft } from 'lucide-react'
import { computeMetrics, fmtPct, fmtDate, StatCard } from './tradeReportHelpers'
import BenchmarkComparison from './BenchmarkComparison'
import BehavioralFlags from './BehavioralFlags'
import EquityCurve from './EquityCurve'
import CostBreakdown from './CostBreakdown'

// computeMetrics is now in tradeReportHelpers.js — kept here as a re-export shim
// so existing tests that import from this file continue to work.
export { computeMetrics, fmtDate }

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
    significance,
  } = computeMetrics(result)

  const startLabel = fmtDate(startDate)
  const endLabel = fmtDate(endDate)
  const periodText =
    startLabel && endLabel ? `${startLabel} - ${endLabel}` : 'N/A'

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
            <StatCard label="SPY Same Period" value={fmtPct(spyReturn)} />
          </div>
        </div>

        <BenchmarkComparison
          netReturnPct={netReturnPct}
          spyReturn={spyReturn}
          qqqReturn={qqqReturn}
          startLabel={startLabel}
          endLabel={endLabel}
        />

        <CostBreakdown
          grossReturnPct={grossReturnPct}
          commissionsPct={commissionsPct}
          slippagePct={slippagePct}
          spreadPct={spreadPct}
          taxPct={taxPct}
          netReturnPct={netReturnPct}
        />

        <EquityCurve equityCurve={result.pnl?.equity_curve} />

        {/* Behavioral Flags */}
        <h2 className="text-2xl font-bold text-white mb-4">
          What Your Trades Are Telling You
        </h2>
        <BehavioralFlags
          dispositionWarning={dispositionWarning}
          dispositionRatio={dispositionRatio}
          avgWinnerDays={avgWinnerDays}
          avgLoserDays={avgLoserDays}
          commissionsPct={commissionsPct}
          slippagePct={slippagePct}
          spreadPct={spreadPct}
          taxPct={taxPct}
          totalCostPct={totalCostPct}
          grossReturnPct={grossReturnPct}
          netReturnPct={netReturnPct}
          winRate={winRate}
          numClosed={numClosed}
          lowSampleWarning={lowSampleWarning}
          overtradingWarning={overtradingWarning}
          openCount={openCount}
          significance={significance}
        />

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
