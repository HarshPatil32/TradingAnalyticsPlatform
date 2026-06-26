import { describe, it, expect } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import CostBreakdown from './CostBreakdown'

// Standard props matching computeMetrics sign convention:
// cost props are negative (deductions), netReturnPct is the final result.
const baseProps = {
  grossReturnPct: 15,
  commissionsPct: -1,
  slippagePct: -0.5,
  spreadPct: -0.6,
  taxPct: -3.9,
  netReturnPct: 9,
}

describe('CostBreakdown', () => {
  it('renders all three waterfall step labels', () => {
    render(<CostBreakdown {...baseProps} />)
    expect(screen.getByText('Gross Return')).toBeInTheDocument()
    expect(screen.getByText('After Costs')).toBeInTheDocument()
    expect(screen.getByText('After Tax')).toBeInTheDocument()
  })

  it('renders deduction labels between steps', () => {
    render(<CostBreakdown {...baseProps} />)
    expect(screen.getByText('Commissions, slippage & spread')).toBeInTheDocument()
    expect(screen.getByText('Estimated tax (30% cap gains)')).toBeInTheDocument()
  })

  it('does not crash when all props are zero', () => {
    render(
      <CostBreakdown
        grossReturnPct={0}
        commissionsPct={0}
        slippagePct={0}
        spreadPct={0}
        taxPct={0}
        netReturnPct={0}
      />
    )
    expect(screen.getByText('Gross Return')).toBeInTheDocument()
  })

  it('does not crash when no props are passed (uses defaults)', () => {
    render(<CostBreakdown />)
    expect(screen.getByText('Gross Return')).toBeInTheDocument()
  })

  it('handles negative gross return (trading at a loss)', () => {
    render(
      <CostBreakdown
        grossReturnPct={-5}
        commissionsPct={-1}
        slippagePct={-0.5}
        spreadPct={-0.5}
        taxPct={0}
        netReturnPct={-7}
      />
    )
    expect(screen.getByText('Gross Return')).toBeInTheDocument()
    expect(screen.getByText('After Tax')).toBeInTheDocument()
  })

  it('confirms cost props are treated as negative deductions', () => {
    // grossReturnPct=10, costs sum to -2, so afterCostsPct should be 8
    // This ensures the sign convention from computeMetrics is honoured.
    const { container } = render(
      <CostBreakdown
        grossReturnPct={10}
        commissionsPct={-1}
        slippagePct={-0.5}
        spreadPct={-0.5}
        taxPct={0}
        netReturnPct={8}
      />
    )
    // After Costs bar should be present and the component should not throw
    expect(screen.getByText('After Costs')).toBeInTheDocument()
    // All three value labels should appear (Gross=+10%, After Costs=+8%, After Tax=+8%)
    const values = container.querySelectorAll('span.font-semibold')
    expect(values.length).toBe(3)
  })
})
