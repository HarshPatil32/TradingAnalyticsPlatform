export const FORMAT_EXAMPLE = `date, symbol, action, price, shares
2024-01-15, AAPL, BUY, 185.50, 10
2024-02-20, AAPL, SELL, 195.20, 10`

export const BROKER_STEPS = [
  {
    name: 'Robinhood',
    steps: [
      'Log in at robinhood.com (web).',
      'Click your profile icon → Account.',
      'Go to Statements & History.',
      'Click Download next to Account History.',
      'Select a date range and download the CSV(Can take a few minutes to a few hours).',
    ],
  },
  {
    name: 'IBKR (Interactive Brokers)',
    steps: [
      'Log in to Client Portal at interactivebrokers.com.',
      'Go to Reports → Statements.',
      'Choose Activity statement and set your date range.',
      'Set format to CSV and click Run.',
      'Download the generated file.',
    ],
  },
  {
    name: 'Schwab',
    steps: [
      'Log in at schwab.com and go to Accounts.',
      'Select History from the left menu.',
      'Set your date range and filter by Trade.',
      'Click Export at the top right of the table.',
      'Choose CSV format and download.',
    ],
  },
]

export const COLUMNS = [
  { name: 'date', desc: 'Trade date (YYYY-MM-DD)' },
  { name: 'symbol', desc: 'Stock ticker symbol' },
  { name: 'action', desc: 'BUY or SELL' },
  { name: 'price', desc: 'Price per share' },
  { name: 'shares', desc: 'Number of shares' },
]

const MAX_FILE_BYTES = 5 * 1024 * 1024

// Returns an error string if the file is invalid, or null if it is acceptable.
export function validateFile(file) {
  if (!file) return null
  const isCSV = file.name.endsWith('.csv') || file.type === 'text/csv'
  if (!isCSV) return 'Only .csv files are supported.'
  if (file.size > MAX_FILE_BYTES) return 'File must be under 5 MB.'
  return null
}
