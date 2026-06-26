// Behavioral flag cards shown in the trade report
import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { FlagIcon, CostRow, fmtPct, fmtDate } from './tradeReportHelpers'
import WinRateCard from './WinRateCard'

export default function BehavioralFlags({
  dispositionWarning,
  dispositionRatio,
  avgWinnerDays,
  avgLoserDays,
  commissionsPct,
  slippagePct,
  spreadPct,
  taxPct,
  totalCostPct,
  grossReturnPct,
  netReturnPct,
  winRate,
  numClosed,
  lowSampleWarning,
  overtradingWarning,
  concentrationWarning,
  openCount,
  openPositions = [],
  significance,
}) {
  const hasCosts =
    commissionsPct !== 0 ||
    slippagePct !== 0 ||
    spreadPct !== 0 ||
    taxPct !== 0

  const openPositionsWithSymbol = openPositions.filter((p) => p.symbol)
  const [showOpenPositions, setShowOpenPositions] = useState(false)

  const concentrationStructured =
    concentrationWarning != null &&
    concentrationWarning.symbol != null &&
    concentrationWarning.concentration_pct != null &&
    concentrationWarning.trade_count != null &&
    concentrationWarning.total_trades != null

  return (
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

      <WinRateCard
        winRate={winRate}
        numClosed={numClosed}
        lowSampleWarning={lowSampleWarning}
        significance={significance}
      />

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

      {/* Concentration risk */}
      {concentrationWarning && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <div className="flex gap-4">
            <FlagIcon variant="warning" />
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-white mb-1">
                {concentrationStructured
                  ? `${(concentrationWarning.concentration_pct * 100).toFixed(1)}% of your trades are in ${concentrationWarning.symbol}`
                  : 'Your trades are heavily concentrated in one symbol'}
              </h3>
              <p className="text-zinc-400 text-sm leading-relaxed">
                {concentrationStructured
                  ? `You placed ${concentrationWarning.trade_count} of your ${concentrationWarning.total_trades} trades in ${concentrationWarning.symbol}. When more than half your activity is in a single stock, a bad outcome in that position can disproportionately hurt your overall results. Consider spreading trades across more symbols.`
                  : (concentrationWarning.message ?? '')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Statistical significance */}
      {significance && (() => {
        const sharpe = significance.sharpe?.sharpe_ratio ?? null
        const isPositiveSig = significance.verdict === 'SIGNIFICANT' && sharpe !== null && sharpe > 0
        const isNegativeSig = significance.verdict === 'SIGNIFICANT' && (sharpe === null || sharpe <= 0)
        const isInsufficient = significance.verdict === 'INSUFFICIENT_DATA'
        const iconVariant = isPositiveSig ? 'success' : isInsufficient ? 'warning' : 'error'
        const headline = isPositiveSig
          ? 'Your edge looks statistically real'
          : isNegativeSig
          ? 'Your losses are statistically consistent, not just bad luck'
          : isInsufficient
          ? 'Not enough closed trades to judge your edge'
          : 'No statistically proven edge yet'

        return (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          <div className="flex gap-4">
            <FlagIcon variant={iconVariant} />
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-white mb-1">{headline}</h3>
              <p className="text-zinc-400 text-sm mb-3">{significance.summary}</p>
              {significance.sharpe?.sharpe_ratio != null && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-zinc-500">Sharpe Ratio</span>
                  <span
                    className={
                      significance.sharpe.sharpe_ratio > 0
                        ? 'text-green-400 font-medium'
                        : 'text-red-400 font-medium'
                    }
                  >
                    {significance.sharpe.sharpe_ratio.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
        )
      })()}

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
              {openPositionsWithSymbol.length > 0 && (
                <div className="mt-4 border-t border-zinc-800 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowOpenPositions((v) => !v)}
                    aria-expanded={showOpenPositions}
                    className="flex items-center gap-2 text-zinc-400 text-sm hover:text-white transition-colors"
                  >
                    <ChevronDown
                      className={`w-4 h-4 transition-transform ${showOpenPositions ? 'rotate-180' : ''}`}
                    />
                    {showOpenPositions ? 'Hide' : 'Show'} {openPositionsWithSymbol.length} open{' '}
                    {openPositionsWithSymbol.length === 1 ? 'position' : 'positions'}
                  </button>
                  {showOpenPositions && (
                    <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                      {openPositionsWithSymbol.map((pos) => (
                        <div
                          key={`${pos.symbol}-${pos.date ?? ''}`}
                          className="flex justify-between items-center text-sm gap-4"
                        >
                          <span className="font-medium text-white">{pos.symbol}</span>
                          <span className="text-zinc-400">{fmtDate(pos.date)}</span>
                          {pos.shares != null && (
                            <span className="text-zinc-400">{pos.shares} shares</span>
                          )}
                          {pos.price != null && (
                            <span className="text-zinc-400">
                              @ ${Number(pos.price).toFixed(2)}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
