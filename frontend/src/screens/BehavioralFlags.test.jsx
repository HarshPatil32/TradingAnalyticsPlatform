import { describe, it, expect } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import BehavioralFlags from './BehavioralFlags'

const baseProps = {
  dispositionWarning: null,
  dispositionRatio: null,
  avgWinnerDays: null,
  avgLoserDays: null,
  commissionsPct: 0,
  slippagePct: 0,
  spreadPct: 0,
  taxPct: 0,
  totalCostPct: 0,
  grossReturnPct: 0,
  netReturnPct: 0,
  winRate: null,
  numClosed: 0,
  lowSampleWarning: null,
  overtradingWarning: null,
  concentrationWarning: null,
  openCount: 0,
  significance: null,
}

describe('BehavioralFlags', () => {
  it('renders an empty container when no flags are present', () => {
    const { container } = render(<BehavioralFlags {...baseProps} />)
    expect(container.firstChild).toBeInTheDocument()
    expect(container.querySelectorAll('.rounded-xl').length).toBe(0)
  })

  it('renders the disposition effect card with ratio and holding days', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        dispositionWarning={{ type: 'disposition_effect', message: 'Fallback message' }}
        dispositionRatio={2.5}
        avgWinnerDays={10}
        avgLoserDays={25}
      />
    )
    expect(
      screen.getByText('You held losers 2.5x longer than winners')
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Your winning trades were closed after an average of 10 days/)
    ).toBeInTheDocument()
  })

  it('falls back to warning message when disposition holding days are missing', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        dispositionWarning={{
          type: 'disposition_effect',
          message: 'You may be holding losers too long.',
        }}
      />
    )
    expect(
      screen.getByText('You held losing trades longer than winning trades')
    ).toBeInTheDocument()
    expect(
      screen.getByText('You may be holding losers too long.')
    ).toBeInTheDocument()
  })

  it('renders the trading costs card when any cost is non-zero', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        commissionsPct={-1}
        totalCostPct={-1}
        grossReturnPct={10}
        netReturnPct={9}
      />
    )
    expect(
      screen.getByText(/Trading costs ate \+1\.0% of your returns/)
    ).toBeInTheDocument()
    expect(screen.getByText('Commissions & Fees')).toBeInTheDocument()
  })

  it('hides the trading costs card when all costs are zero', () => {
    render(<BehavioralFlags {...baseProps} />)
    expect(
      screen.queryByText(/Trading costs ate/)
    ).not.toBeInTheDocument()
  })

  it('renders the win rate card with low-sample note', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        winRate={45}
        numClosed={30}
        lowSampleWarning={{ type: 'insufficient_data', message: 'Low sample' }}
      />
    )
    expect(screen.getByText('Win rate')).toBeInTheDocument()
    expect(screen.getByText('45.0%')).toBeInTheDocument()
    expect(screen.getByText('Insufficient sample')).toBeInTheDocument()
    expect(
      screen.getByText(/Not enough data yet to call this a proven strategy/)
    ).toBeInTheDocument()
  })

  it('renders the overtrading card', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        overtradingWarning={{
          type: 'overtrading',
          message: 'You made 50 trades in 30 days.',
        }}
      />
    )
    expect(
      screen.getByText("You're trading more than your edge justifies")
    ).toBeInTheDocument()
    expect(screen.getByText('You made 50 trades in 30 days.')).toBeInTheDocument()
    expect(screen.getByText('Consider reducing trade frequency')).toBeInTheDocument()
  })

  it('renders the concentration risk card with structured warning data', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        concentrationWarning={{
          type: 'concentration_risk',
          symbol: 'AAPL',
          trade_count: 3,
          total_trades: 4,
          concentration_pct: 0.75,
          message: 'Backend fallback message',
        }}
      />
    )
    expect(screen.getByText('75.0% of your trades are in AAPL')).toBeInTheDocument()
    expect(
      screen.getByText(/You placed 3 of your 4 trades in AAPL/)
    ).toBeInTheDocument()
  })

  it('falls back to concentration warning message when structured fields are missing', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        concentrationWarning={{
          type: 'concentration_risk',
          message: '75% of your trades are in AAPL (3 of 4).',
        }}
      />
    )
    expect(
      screen.getByText('Your trades are heavily concentrated in one symbol')
    ).toBeInTheDocument()
    expect(
      screen.getByText('75% of your trades are in AAPL (3 of 4).')
    ).toBeInTheDocument()
  })

  it('uses fallback copy when only some structured concentration fields are present', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        concentrationWarning={{
          type: 'concentration_risk',
          symbol: 'AAPL',
          concentration_pct: 0.75,
          message: 'Partial data from backend.',
        }}
      />
    )
    expect(
      screen.getByText('Your trades are heavily concentrated in one symbol')
    ).toBeInTheDocument()
    expect(screen.getByText('Partial data from backend.')).toBeInTheDocument()
    expect(
      screen.queryByText('75.0% of your trades are in AAPL')
    ).not.toBeInTheDocument()
  })

  it('renders an empty body when concentration fallback message is missing', () => {
    const { container } = render(
      <BehavioralFlags
        {...baseProps}
        concentrationWarning={{ type: 'concentration_risk' }}
      />
    )
    expect(
      screen.getByText('Your trades are heavily concentrated in one symbol')
    ).toBeInTheDocument()
    const body = container.querySelector('.leading-relaxed')
    expect(body?.textContent).toBe('')
  })

  it('renders a positive statistical significance card', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        significance={{
          verdict: 'SIGNIFICANT',
          summary: 'Your returns look real.',
          sharpe: { sharpe_ratio: 1.2 },
        }}
      />
    )
    expect(screen.getByText('Your edge looks statistically real')).toBeInTheDocument()
    expect(screen.getByText('Your returns look real.')).toBeInTheDocument()
    expect(screen.getByText('1.20')).toBeInTheDocument()
  })

  it('renders a negative statistical significance card', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        significance={{
          verdict: 'SIGNIFICANT',
          summary: 'Losses are consistent.',
          sharpe: { sharpe_ratio: -0.8 },
        }}
      />
    )
    expect(
      screen.getByText('Your losses are statistically consistent, not just bad luck')
    ).toBeInTheDocument()
  })

  it('renders an insufficient-data significance card', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        significance={{
          verdict: 'INSUFFICIENT_DATA',
          summary: 'Need more closed trades.',
        }}
      />
    )
    expect(
      screen.getByText('Not enough closed trades to judge your edge')
    ).toBeInTheDocument()
  })

  it('renders a no-edge significance card for other verdicts', () => {
    render(
      <BehavioralFlags
        {...baseProps}
        significance={{
          verdict: 'NOT_SIGNIFICANT',
          summary: 'Could still be luck.',
        }}
      />
    )
    expect(screen.getByText('No statistically proven edge yet')).toBeInTheDocument()
  })

  it('renders the open positions card for multiple positions', () => {
    render(<BehavioralFlags {...baseProps} openCount={3} />)
    expect(screen.getByText('3 open positions')).toBeInTheDocument()
    expect(screen.getByText(/haven't been closed yet/)).toBeInTheDocument()
  })

  it('uses singular copy for one open position', () => {
    render(<BehavioralFlags {...baseProps} openCount={1} />)
    expect(screen.getByText('1 open position')).toBeInTheDocument()
    expect(screen.getByText(/hasn't been closed yet/)).toBeInTheDocument()
  })
})
