import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen, fireEvent } from '@testing-library/react'
import { computeMetrics, fmtDate } from './tradeReportHelpers'
import TradeReport from './TradeReport'

function makeResult(overrides = {}) {
  return {
    trades: [],
    pnl: {
      trade_pnl: [],
      total_pnl: 0,
      total_return_pct: 0,
      avg_holding_days_winners: null,
      avg_holding_days_losers: null,
    },
    warnings: [],
    notices: [],
    spy_benchmark: null,
    qqq_benchmark: null,
    commissions: null,
    slippage: null,
    bid_ask_spread: null,
    ...overrides,
  }
}

describe('computeMetrics', () => {
  it('handles grossReturnPct === 0 without dividing by zero', () => {
    const metrics = computeMetrics(makeResult())
    expect(metrics.netReturnPct).toBe(0)
    expect(metrics.commissionsPct).toBe(0)
    expect(metrics.slippagePct).toBe(0)
  })

  it('handles empty warnings array', () => {
    const metrics = computeMetrics(makeResult({ warnings: [] }))
    expect(metrics.dispositionWarning).toBeNull()
    expect(metrics.overtradingWarning).toBeNull()
    expect(metrics.concentrationWarning).toBeNull()
    expect(metrics.lowSampleWarning).toBeNull()
  })

  it('extracts concentrationWarning from warnings', () => {
    const warning = {
      type: 'concentration_risk',
      symbol: 'AAPL',
      concentration_pct: 0.75,
      message: '75% of trades in AAPL',
    }
    const metrics = computeMetrics(makeResult({ warnings: [warning] }))
    expect(metrics.concentrationWarning).toEqual(warning)
  })

  it('handles empty notices array', () => {
    const metrics = computeMetrics(makeResult({ notices: [] }))
    expect(metrics.openCount).toBe(0)
  })

  it('only counts unclosed_position notices in openCount', () => {
    const metrics = computeMetrics(makeResult({
      notices: [
        { type: 'unclosed_position', message: 'Open: AAPL' },
        { type: 'some_other_notice', message: 'Other' },
      ],
    }))
    expect(metrics.openCount).toBe(1)
  })

  it('returns openPositions array from unclosed_position notices', () => {
    const notice = {
      type: 'unclosed_position',
      symbol: 'AAPL',
      date: '2024-01-15',
      price: 150.0,
      shares: 10,
    }
    const metrics = computeMetrics(makeResult({ notices: [notice] }))
    expect(metrics.openCount).toBe(1)
    expect(metrics.openPositions).toEqual([notice])
  })

  it('does not apply tax when grossPnlUsd < 10', () => {
    const metrics = computeMetrics(makeResult({
      pnl: { trade_pnl: [], total_pnl: 5, total_return_pct: 5 },
    }))
    expect(metrics.taxPct).toBe(0)
  })

  it('applies tax estimate when grossPnlUsd >= 10', () => {
    const metrics = computeMetrics(makeResult({
      pnl: { trade_pnl: [], total_pnl: 100, total_return_pct: 10 },
    }))
    expect(metrics.taxPct).toBeLessThan(0)
  })
})

describe('fmtDate', () => {
  it('returns null for null input', () => {
    expect(fmtDate(null)).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(fmtDate('')).toBeNull()
  })

  it('formats a valid date string', () => {
    const result = fmtDate('2024-01-15')
    expect(result).toMatch(/Jan/)
    expect(result).toMatch(/15/)
    expect(result).toMatch(/2024/)
  })

  it('returns the original string for a malformed date', () => {
    expect(fmtDate('not-a-date')).toBe('not-a-date')
    expect(fmtDate('unknown date')).toBe('unknown date')
  })
})

describe('TradeReport', () => {
  it('calls onBack and renders nothing when result is null', () => {
    const onBack = vi.fn()
    const { container } = render(<TradeReport result={null} onBack={onBack} />)
    expect(onBack).toHaveBeenCalledTimes(1)
    expect(container.firstChild).toBeNull()
  })

  it('shows N/A in the SPY stat card when benchmark data is missing', () => {
    const result = makeResult({ spy_benchmark: null, qqq_benchmark: null })
    render(<TradeReport result={result} onBack={vi.fn()} />)
    // Multiple stat cards may show N/A — just confirm at least one appears
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)
  })

  it('does not render the benchmark section when both spy and qqq are null', () => {
    const result = makeResult({ spy_benchmark: null, qqq_benchmark: null })
    render(<TradeReport result={result} onBack={vi.fn()} />)
    expect(screen.queryByText(/Benchmark Comparison/i)).not.toBeInTheDocument()
  })

  it('renders the benchmark section when spy data is present', () => {
    const result = makeResult({
      spy_benchmark: { total_return_pct: 12.5, start_date: '2024-01-01', end_date: '2024-12-31' },
    })
    render(<TradeReport result={result} onBack={vi.fn()} />)
    expect(screen.getByText(/Benchmark Comparison/i)).toBeInTheDocument()
  })

  it('renders the upgrade block when isPro is false', () => {
    render(<TradeReport result={makeResult()} onBack={vi.fn()} isPro={false} />)
    expect(screen.getByText('Upgrade to Pro')).toBeInTheDocument()
    expect(screen.getByText('Upgrade Now')).toBeInTheDocument()
  })

  it('hides the upgrade block when isPro is true', () => {
    render(<TradeReport result={makeResult()} onBack={vi.fn()} isPro />)
    expect(screen.queryByText('Upgrade to Pro')).not.toBeInTheDocument()
    expect(screen.queryByText('Upgrade Now')).not.toBeInTheDocument()
  })

  it('calls onUpgrade when Upgrade Now is clicked', () => {
    const onUpgrade = vi.fn()
    render(
      <TradeReport result={makeResult()} onBack={vi.fn()} isPro={false} onUpgrade={onUpgrade} />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Upgrade Now' }))
    expect(onUpgrade).toHaveBeenCalledTimes(1)
  })

  it('dismisses the upgrade block when Save These Results is clicked', () => {
    const onSaveResults = vi.fn()
    render(
      <TradeReport
        result={makeResult()}
        onBack={vi.fn()}
        isPro={false}
        onSaveResults={onSaveResults}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save These Results (Free)' }))
    expect(onSaveResults).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Upgrade to Pro')).not.toBeInTheDocument()
  })
})
