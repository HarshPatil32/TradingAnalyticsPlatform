import { describe, it, expect } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import WinRateCard, { deriveWinRateVerdict } from './WinRateCard'

describe('deriveWinRateVerdict', () => {
  it('returns insufficient sample when trade count is below threshold', () => {
    expect(
      deriveWinRateVerdict({ winRate: 45, numClosed: 10, lowSampleWarning: null, significance: null })
        .label
    ).toBe('Insufficient sample')
  })

  it('returns below chance for low win rate with enough trades', () => {
    expect(
      deriveWinRateVerdict({ winRate: 45, numClosed: 50, lowSampleWarning: null, significance: null })
        .label
    ).toBe('Below chance')
  })

  it('returns marginal for win rate above 50% without significance', () => {
    expect(
      deriveWinRateVerdict({
        winRate: 52,
        numClosed: 50,
        lowSampleWarning: null,
        significance: { winrate: { significant: false } },
      }).label
    ).toBe('Marginal')
  })

  it('returns marginal for exactly 50% win rate', () => {
    const verdict = deriveWinRateVerdict({
      winRate: 50,
      numClosed: 50,
      lowSampleWarning: null,
      significance: null,
    })
    expect(verdict.label).toBe('Marginal')
    expect(verdict.explanation).toMatch(/at or above 50%/)
  })

  it('returns statistically sufficient at the 55% threshold', () => {
    expect(
      deriveWinRateVerdict({
        winRate: 55,
        numClosed: 50,
        lowSampleWarning: null,
        significance: { winrate: { significant: true } },
      }).label
    ).toBe('Statistically sufficient')
  })

  it('returns marginal for high win rate when significance is missing', () => {
    expect(
      deriveWinRateVerdict({
        winRate: 58,
        numClosed: 50,
        lowSampleWarning: null,
        significance: null,
      }).label
    ).toBe('Marginal')
  })
})

describe('WinRateCard', () => {
  it('renders nothing when winRate is null', () => {
    const { container } = render(
      <WinRateCard
        winRate={null}
        numClosed={0}
        lowSampleWarning={null}
        significance={null}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders insufficient sample verdict for small samples', () => {
    render(
      <WinRateCard
        winRate={45}
        numClosed={10}
        lowSampleWarning={null}
        significance={null}
      />
    )
    expect(screen.getByText('45.0%')).toBeInTheDocument()
    expect(screen.getByText('Insufficient sample')).toBeInTheDocument()
    expect(
      screen.getByText(/Only 10 closed trades — at least 30 are recommended/)
    ).toBeInTheDocument()
  })

  it('renders below chance verdict for low win rate with enough trades', () => {
    render(
      <WinRateCard
        winRate={45}
        numClosed={50}
        lowSampleWarning={null}
        significance={null}
      />
    )
    expect(screen.getByText('45.0%')).toBeInTheDocument()
    expect(screen.getByText('Below chance')).toBeInTheDocument()
    expect(
      screen.getByText(/Under half your trades were profitable/)
    ).toBeInTheDocument()
  })

  it('renders marginal verdict when win rate is above 50% but not significant', () => {
    render(
      <WinRateCard
        winRate={52}
        numClosed={50}
        lowSampleWarning={null}
        significance={{ winrate: { significant: false } }}
      />
    )
    expect(screen.getByText('Marginal')).toBeInTheDocument()
    expect(
      screen.getByText(/has not been proven statistically significant yet/)
    ).toBeInTheDocument()
  })

  it('renders marginal verdict at exactly 50% win rate', () => {
    render(
      <WinRateCard
        winRate={50}
        numClosed={50}
        lowSampleWarning={null}
        significance={null}
      />
    )
    expect(screen.getByText('50.0%')).toBeInTheDocument()
    expect(screen.getByText('Marginal')).toBeInTheDocument()
    expect(screen.getByText(/at or above 50%/)).toBeInTheDocument()
  })

  it('renders marginal verdict for high win rate when significance is missing', () => {
    render(
      <WinRateCard
        winRate={58}
        numClosed={50}
        lowSampleWarning={null}
        significance={null}
      />
    )
    expect(screen.getByText('58.0%')).toBeInTheDocument()
    expect(screen.getByText('Marginal')).toBeInTheDocument()
  })

  it('renders statistically sufficient verdict at the 55% threshold', () => {
    render(
      <WinRateCard
        winRate={55}
        numClosed={50}
        lowSampleWarning={null}
        significance={{ winrate: { significant: true } }}
      />
    )
    expect(screen.getByText('55.0%')).toBeInTheDocument()
    expect(screen.getByText('Statistically sufficient')).toBeInTheDocument()
  })

  it('renders statistically sufficient verdict for proven high win rate', () => {
    render(
      <WinRateCard
        winRate={62}
        numClosed={50}
        lowSampleWarning={null}
        significance={{ winrate: { significant: true } }}
      />
    )
    expect(screen.getByText('Statistically sufficient')).toBeInTheDocument()
    expect(
      screen.getByText(/statistically better than chance at the 5% level/)
    ).toBeInTheDocument()
  })

  it('renders low-sample note when lowSampleWarning is present', () => {
    render(
      <WinRateCard
        winRate={45}
        numClosed={30}
        lowSampleWarning={{ type: 'insufficient_data', message: 'Low sample' }}
        significance={null}
      />
    )
    expect(screen.getByText('Insufficient sample')).toBeInTheDocument()
    expect(
      screen.getByText(/Not enough data yet to call this a proven strategy/)
    ).toBeInTheDocument()
  })
})
