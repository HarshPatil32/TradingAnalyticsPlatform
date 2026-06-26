import { describe, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import BenchmarkBar, { CustomTooltip } from './BenchmarkBar'

// Mock ResponsiveContainer so recharts renders children at a fixed size in jsdom
vi.mock('recharts', async () => {
  const recharts = await vi.importActual('recharts')
  return {
    ...recharts,
    ResponsiveContainer: ({ children }) => (
      <div style={{ width: 800, height: 200 }}>{children}</div>
    ),
  }
})

describe('BenchmarkBar', () => {
  it('renders nothing when only one data point is available', () => {
    const { container } = render(
      <BenchmarkBar userReturn={5} spyReturn={null} qqqReturn={null} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders the label when spy data is present', () => {
    render(<BenchmarkBar userReturn={5} spyReturn={10} qqqReturn={null} />)
    expect(screen.getByText('Return Comparison')).toBeInTheDocument()
  })

  it('renders a chart when all three values are provided', () => {
    const { container } = render(
      <BenchmarkBar userReturn={5} spyReturn={10} qqqReturn={8} />
    )
    expect(screen.getByText('Return Comparison')).toBeInTheDocument()
    expect(container.firstChild).not.toBeNull()
  })

  it('renders with all negative returns', () => {
    render(<BenchmarkBar userReturn={-5} spyReturn={-3} qqqReturn={-8} />)
    expect(screen.getByText('Return Comparison')).toBeInTheDocument()
  })

  it('renders a chart when qqq is missing but spy is present', () => {
    const { container } = render(
      <BenchmarkBar userReturn={2} spyReturn={7} qqqReturn={null} />
    )
    expect(screen.getByText('Return Comparison')).toBeInTheDocument()
    expect(container.firstChild).not.toBeNull()
  })
})

describe('CustomTooltip', () => {
  it('renders the name and formatted value for a positive return', () => {
    render(
      <CustomTooltip
        active={true}
        payload={[{ payload: { name: 'SPY' }, value: 10 }]}
      />
    )
    expect(screen.getByText('SPY: +10.0%')).toBeInTheDocument()
  })

  it('renders correctly for a negative return', () => {
    render(
      <CustomTooltip
        active={true}
        payload={[{ payload: { name: 'Your Strategy' }, value: -3.5 }]}
      />
    )
    expect(screen.getByText('Your Strategy: -3.5%')).toBeInTheDocument()
  })

  it('renders nothing when inactive', () => {
    const { container } = render(
      <CustomTooltip
        active={false}
        payload={[{ payload: { name: 'SPY' }, value: 10 }]}
      />
    )
    expect(container.firstChild).toBeNull()
  })
})
