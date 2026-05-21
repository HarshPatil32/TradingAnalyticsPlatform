import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen, fireEvent, act } from '@testing-library/react'
import axios from 'axios'
import { validateFile } from './CSVUpload.constants'
import CSVUpload, { ResultsPanel } from './CSVUpload'

vi.mock('axios', () => ({
  default: { post: vi.fn() },
}))

function makeFile(name, type, size) {
  const file = new File([''], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

const MB5 = 5 * 1024 * 1024

describe('validateFile', () => {
  it('returns null for a valid CSV by extension', () => {
    expect(validateFile(makeFile('trades.csv', 'text/csv', 100))).toBeNull()
  })

  it('returns null for a file with text/csv MIME type and no .csv extension', () => {
    expect(validateFile(makeFile('trades', 'text/csv', 100))).toBeNull()
  })

  it('returns an error for a non-CSV file', () => {
    expect(validateFile(makeFile('trades.xlsx', 'application/vnd.ms-excel', 100))).toBe(
      'Only .csv files are supported.'
    )
  })

  it('returns an error for a file over 5 MB', () => {
    expect(validateFile(makeFile('big.csv', 'text/csv', MB5 + 1))).toBe('File must be under 5 MB.')
  })

  it('returns null for a file exactly at 5 MB', () => {
    expect(validateFile(makeFile('edge.csv', 'text/csv', MB5))).toBeNull()
  })

  it('returns null for a falsy input', () => {
    expect(validateFile(null)).toBeNull()
  })
})

describe('CSVUpload component', () => {
  it('renders the example CSV download link with correct attributes', () => {
    render(<CSVUpload />)
    const link = screen.getByRole('link', { name: /download example/i })
    expect(link).toHaveAttribute('href', '/example-trades.csv')
    expect(link).toHaveAttribute('download', 'example-trades.csv')
  })
})

describe('ResultsPanel', () => {
  const baseDetailed = {
    format: 'detailed',
    pnl: { total_pnl: 100, total_return_pct: 5 },
    trades: [{}],
    warnings: [],
    notices: [],
  }

  it('shows warning messages in yellow', () => {
    const result = {
      ...baseDetailed,
      warnings: [{ type: 'duplicate', level: 'warning', message: 'Duplicate trade detected.' }],
    }
    render(<ResultsPanel result={result} />)
    const msg = screen.getByText('Duplicate trade detected.')
    expect(msg).toBeInTheDocument()
    expect(msg).toHaveClass('text-yellow-400')
  })

  it('shows notice messages in zinc', () => {
    const result = {
      ...baseDetailed,
      notices: [{ type: 'unclosed_position', level: 'info', message: 'Open position: AAPL BUY on 2024-01-15 (no matching SELL yet)' }],
    }
    render(<ResultsPanel result={result} />)
    const msg = screen.getByText(/Open position/)
    expect(msg).toBeInTheDocument()
    expect(msg).toHaveClass('text-zinc-400')
  })

  it('shows no feedback section when there are no warnings or notices', () => {
    render(<ResultsPanel result={baseDetailed} />)
    expect(screen.queryByText(/duplicate/i)).not.toBeInTheDocument()
  })

  it('shows multiple warnings', () => {
    const result = {
      ...baseDetailed,
      warnings: [
        { type: 'duplicate', level: 'warning', message: 'First warning.' },
        { type: 'unmatched_sell', level: 'warning', message: 'Second warning.' },
      ],
    }
    render(<ResultsPanel result={result} />)
    expect(screen.getByText('First warning.')).toBeInTheDocument()
    expect(screen.getByText('Second warning.')).toBeInTheDocument()
  })

  it('shows warnings in summary format', () => {
    const result = {
      format: 'summary',
      summary: { initial_capital: 1000, final_balance: 1100, win_rate: 0.6, num_trades: 5 },
      warnings: [{ type: 'low_trades', level: 'warning', message: 'Too few trades for reliable conclusions.' }],
      notices: [],
    }
    render(<ResultsPanel result={result} />)
    expect(screen.getByText('Too few trades for reliable conclusions.')).toBeInTheDocument()
  })

  it('renders fallback for unknown format and still shows warnings', () => {
    const result = {
      format: 'unknown',
      warnings: [{ type: 'test', level: 'warning', message: 'A fallback warning.' }],
      notices: [],
    }
    render(<ResultsPanel result={result} />)
    expect(screen.getByText(/Analysis complete/i)).toBeInTheDocument()
    expect(screen.getByText('A fallback warning.')).toBeInTheDocument()
  })

  it('silently skips warning objects with no message', () => {
    const result = {
      ...baseDetailed,
      warnings: [{ type: 'broken' }],
    }
    const { container } = render(<ResultsPanel result={result} />)
    expect(container.querySelectorAll('.text-yellow-400')).toHaveLength(0)
  })
})

describe('CSVUpload loading state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a spinner while analyzing and hides it when done', async () => {
    let resolvePost
    axios.post.mockImplementation(() => new Promise(res => { resolvePost = res }))

    render(<CSVUpload />)

    fireEvent.change(screen.getByPlaceholderText(/paste csv data/i), {
      target: { value: 'date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,10' },
    })

    fireEvent.click(screen.getByRole('button', { name: /analyze trades/i }))

    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /analyzing/i })).toBeDisabled()

    await act(async () => {
      resolvePost({ data: { format: 'detailed', pnl: { total_pnl: 0, total_return_pct: 0 }, trades: [], warnings: [], notices: [] } })
    })

    expect(document.querySelector('.animate-spin')).not.toBeInTheDocument()
    // button label reverts even though it stays disabled (input was cleared on success)
    expect(screen.getByRole('button', { name: /analyze trades/i })).toBeInTheDocument()
  })

  it('hides the spinner if the request fails', async () => {
    axios.post.mockRejectedValue(new Error('Network error'))

    render(<CSVUpload />)

    fireEvent.change(screen.getByPlaceholderText(/paste csv data/i), {
      target: { value: 'date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,10' },
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /analyze trades/i }))
    })

    expect(document.querySelector('.animate-spin')).not.toBeInTheDocument()
    // input is preserved on error, so button re-enables
    expect(screen.getByRole('button', { name: /analyze trades/i })).not.toBeDisabled()
  })
})
