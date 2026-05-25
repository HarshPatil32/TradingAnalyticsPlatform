// Benchmark comparison section for TradeReport
import { BenchmarkCard, fmtPct } from './tradeReportHelpers'
import BenchmarkBar from './BenchmarkBar'

export default function BenchmarkComparison({
  netReturnPct,
  spyReturn,
  qqqReturn,
  startLabel,
  endLabel,
}) {
  if (spyReturn == null && qqqReturn == null) return null

  const spyBeatsStrategy = spyReturn != null && spyReturn > netReturnPct
  const qqqBeatsStrategy = qqqReturn != null && qqqReturn > netReturnPct

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-4">Benchmark Comparison</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <BenchmarkCard label="Your Strategy" value={fmtPct(netReturnPct)} />
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
      <BenchmarkBar
        userReturn={netReturnPct}
        spyReturn={spyReturn}
        qqqReturn={qqqReturn}
      />
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
  )
}
