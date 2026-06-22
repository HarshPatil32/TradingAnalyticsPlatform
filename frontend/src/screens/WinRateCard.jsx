import { FlagIcon, fmtRate } from './tradeReportHelpers'

const MIN_TRADES_FOR_SUFFICIENCY = 30
const GOOD_WIN_RATE_THRESHOLD = 55
const CHANCE_WIN_RATE_THRESHOLD = 50

export function deriveWinRateVerdict({ winRate, numClosed, lowSampleWarning, significance }) {
  if (numClosed < MIN_TRADES_FOR_SUFFICIENCY || lowSampleWarning) {
    return {
      label: 'Insufficient sample',
      iconVariant: 'warning',
      valueClass: 'text-white',
      pillClass: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
      explanation:
        numClosed < MIN_TRADES_FOR_SUFFICIENCY
          ? `Only ${numClosed} closed trades — at least ${MIN_TRADES_FOR_SUFFICIENCY} are recommended before drawing conclusions.`
          : `With ${numClosed} closed trades, this sample is still too small to judge whether your win rate reflects skill or luck.`,
    }
  }

  if (significance?.winrate?.significant === true && winRate >= GOOD_WIN_RATE_THRESHOLD) {
    return {
      label: 'Statistically sufficient',
      iconVariant: 'success',
      valueClass: 'text-green-400',
      pillClass: 'text-green-400 bg-green-500/10 border-green-500/20',
      explanation:
        'Your win rate is above 55% and statistically better than chance at the 5% level.',
    }
  }

  if (winRate >= CHANCE_WIN_RATE_THRESHOLD) {
    return {
      label: 'Marginal',
      iconVariant: 'warning',
      valueClass: 'text-yellow-400',
      pillClass: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
      explanation:
        'Your win rate is at or above 50%, but it has not been proven statistically significant yet.',
    }
  }

  return {
    label: 'Below chance',
    iconVariant: 'error',
    valueClass: 'text-red-400',
    pillClass: 'text-red-400 bg-red-500/10 border-red-500/20',
    explanation: 'Under half your trades were profitable — below a random coin flip.',
  }
}

export default function WinRateCard({
  winRate,
  numClosed,
  lowSampleWarning,
  significance,
}) {
  if (winRate == null) return null

  const verdict = deriveWinRateVerdict({
    winRate,
    numClosed,
    lowSampleWarning,
    significance,
  })

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <div className="flex gap-4">
        <FlagIcon variant={verdict.iconVariant} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-2">
            <h3 className="font-semibold text-white">Win rate</h3>
            <span className={`text-2xl font-bold ${verdict.valueClass}`}>
              {fmtRate(winRate)}
            </span>
            <span
              className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${verdict.pillClass}`}
            >
              {verdict.label}
            </span>
          </div>
          <p className="text-zinc-400 text-sm leading-relaxed">{verdict.explanation}</p>
          {lowSampleWarning && (
            <p className="text-zinc-500 text-sm italic mt-2">
              Not enough data yet to call this a proven strategy
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
