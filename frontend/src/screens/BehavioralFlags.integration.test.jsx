import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import { computeMetrics } from './tradeReportHelpers'
import TradeReport from './TradeReport'

// Simulates a real API response where AAPL is 75% of trades.
const concentratedApiResult = {
  trades: [
    { date: '2024-01-01', symbol: 'AAPL', action: 'BUY', price: 100, shares: 10 },
    { date: '2024-01-02', symbol: 'AAPL', action: 'SELL', price: 110, shares: 10 },
    { date: '2024-01-03', symbol: 'AAPL', action: 'BUY', price: 105, shares: 10 },
    { date: '2024-01-04', symbol: 'MSFT', action: 'BUY', price: 200, shares: 5 },
  ],
  pnl: {
    trade_pnl: [
      { symbol: 'AAPL', pnl: 50 },
      { symbol: 'MSFT', pnl: -10 },
    ],
    total_pnl: 40,
    total_return_pct: 4,
    avg_holding_days_winners: 10,
    avg_holding_days_losers: 20,
  },
  warnings: [
    {
      type: 'concentration_risk',
      level: 'warning',
      message:
        '75.0% of your trades are in AAPL (3 of 4). Having more than half your trades in a single symbol increases exposure to that asset. Consider diversifying across more symbols to reduce concentration risk.',
      symbol: 'AAPL',
      trade_count: 3,
      total_trades: 4,
      concentration_pct: 0.75,
    },
  ],
  notices: [],
  spy_benchmark: null,
  qqq_benchmark: null,
  commissions: { total_commission_usd: 4 },
  slippage: { total_slippage_usd: 2 },
  bid_ask_spread: { total_spread_usd: 1 },
}

describe('BehavioralFlags integration', () => {
  it('wires concentrationWarning from API result through TradeReport to the UI', () => {
    const metrics = computeMetrics(concentratedApiResult)
    expect(metrics.concentrationWarning).not.toBeNull()
    expect(metrics.concentrationWarning.symbol).toBe('AAPL')
    expect(metrics.concentrationWarning.concentration_pct).toBe(0.75)

    render(<TradeReport result={concentratedApiResult} onBack={vi.fn()} />)

    expect(screen.getByText('75.0% of your trades are in AAPL')).toBeInTheDocument()
    expect(screen.getByText(/You placed 3 of your 4 trades in AAPL/)).toBeInTheDocument()
    expect(screen.getByText(/What Your Trades Are Telling You/)).toBeInTheDocument()
  })
})
