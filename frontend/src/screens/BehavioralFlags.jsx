// Behavioral flag cards shown in the trade report
import { FlagIcon, CostRow, fmtPct } from './tradeReportHelpers'

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
  openCount,
}) {
  const hasCosts =
    commissionsPct !== 0 ||
    slippagePct !== 0 ||
    spreadPct !== 0 ||
    taxPct !== 0

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
  )
}
