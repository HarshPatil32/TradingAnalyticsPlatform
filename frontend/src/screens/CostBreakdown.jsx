// Waterfall display: gross return → after costs → after tax
import { fmtPct } from './tradeReportHelpers'

// Cost props (commissionsPct, slippagePct, spreadPct, taxPct) are negative percentages
// as returned by computeMetrics — they represent deductions from gross return.
export default function CostBreakdown({
  grossReturnPct = 0,
  commissionsPct = 0,
  slippagePct = 0,
  spreadPct = 0,
  taxPct = 0,
  netReturnPct = 0,
}) {
  const afterCostsPct = grossReturnPct + commissionsPct + slippagePct + spreadPct
  const costDeductionPct = commissionsPct + slippagePct + spreadPct

  // Each step carries its own deduction label so adding/reordering steps stays safe.
  const steps = [
    { label: 'Gross Return', value: grossReturnPct, deductionBefore: null },
    {
      label: 'After Costs',
      value: afterCostsPct,
      deductionBefore: { label: 'Commissions, slippage & spread', value: costDeductionPct },
    },
    {
      label: 'After Tax',
      value: netReturnPct,
      deductionBefore: { label: 'Estimated tax (30% cap gains)', value: taxPct },
    },
  ]

  const maxAbs = Math.max(...steps.map((s) => Math.abs(s.value)), 0.01)
  const barWidth = (val) =>
    isNaN(val) ? 0 : Math.min((Math.abs(val) / maxAbs) * 100, 100)
  const barColor = (val) => (val >= 0 ? 'bg-green-500' : 'bg-red-500')
  const textColor = (val) => (val >= 0 ? 'text-green-400' : 'text-red-400')

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
      <h2 className="text-lg font-semibold text-white mb-6">Return Breakdown</h2>
      <div className="space-y-1">
        {steps.map((step) => (
          <div key={step.label}>
            {step.deductionBefore && (
              <div className="flex items-center gap-2 py-2 pl-2">
                <span className="text-zinc-600 text-xs">▼</span>
                <span className="text-zinc-500 text-xs">{step.deductionBefore.label}</span>
                <span className={`text-xs font-medium ml-auto ${textColor(step.deductionBefore.value)}`}>
                  {fmtPct(step.deductionBefore.value)}
                </span>
              </div>
            )}
            <div className="flex items-center gap-4">
              <span className="text-zinc-400 text-sm w-28 shrink-0">{step.label}</span>
              <div className="flex-1 bg-zinc-800 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-full rounded-full ${barColor(step.value)}`}
                  style={{ width: `${barWidth(step.value)}%` }}
                />
              </div>
              <span className={`text-sm font-semibold w-16 text-right ${textColor(step.value)}`}>
                {fmtPct(step.value)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
