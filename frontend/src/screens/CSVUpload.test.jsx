import { describe, it, expect } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import { validateFile } from './CSVUpload.constants'
import CSVUpload from './CSVUpload'

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
