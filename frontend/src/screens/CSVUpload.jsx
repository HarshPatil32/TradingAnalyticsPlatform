// Upload screen: drag-and-drop or file picker plus paste, then calls /analyze-trades
import { useState, useRef } from 'react'
import { UploadCloud, FileText } from 'lucide-react'
import axios from 'axios'
import { API_URL } from '../config'

const FORMAT_EXAMPLE = `date, symbol, action, price, shares
2024-01-15, AAPL, BUY, 185.50, 10
2024-02-20, AAPL, SELL, 195.20, 10`

const COLUMNS = [
  { name: 'date', desc: 'Trade date (YYYY-MM-DD)' },
  { name: 'symbol', desc: 'Stock ticker symbol' },
  { name: 'action', desc: 'BUY or SELL' },
  { name: 'price', desc: 'Price per share' },
  { name: 'shares', desc: 'Number of shares' },
]

function ResultsPanel({ result }) {
  if (result.format === 'detailed') {
    const pnl = result.pnl ?? {}
    const totalPnl = pnl.total_pnl ?? 0
    const returnPct = pnl.total_return_pct ?? 0
    const isPos = totalPnl >= 0
    return (
      <div className="mt-8 bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <p className="text-green-400 font-semibold">Analysis complete — detailed trade log</p>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-zinc-800 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Total P&amp;L</p>
            <p className={`text-xl font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
              {isPos ? '+' : ''}{totalPnl.toFixed(2)}
            </p>
          </div>
          <div className="bg-zinc-800 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Total Return</p>
            <p className={`text-xl font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
              {isPos ? '+' : ''}{returnPct.toFixed(2)}%
            </p>
          </div>
        </div>
        {result.trades?.length > 0 && (
          <p className="text-zinc-400 text-sm">{result.trades.length} trades analysed.</p>
        )}
      </div>
    )
  }

  if (result.format === 'summary') {
    const s = result.summary ?? {}
    const ret = s.initial_capital && s.final_balance != null
      ? (((s.final_balance - s.initial_capital) / s.initial_capital) * 100).toFixed(2)
      : null
    const isPos = s.final_balance != null && s.initial_capital != null && s.final_balance >= s.initial_capital
    return (
      <div className="mt-8 bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <p className="text-green-400 font-semibold">Analysis complete — summary report</p>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-zinc-800 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Final Balance</p>
            <p className={`text-xl font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
              ${s.final_balance?.toLocaleString()}
            </p>
          </div>
          <div className="bg-zinc-800 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Return</p>
            <p className={`text-xl font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
              {ret != null ? `${isPos ? '+' : ''}${ret}%` : 'N/A'}
            </p>
          </div>
          <div className="bg-zinc-800 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Win Rate</p>
            <p className="text-xl font-bold text-white">
              {s.win_rate != null ? `${(s.win_rate * 100).toFixed(1)}%` : 'N/A'}
            </p>
          </div>
          <div className="bg-zinc-800 rounded-lg p-4">
            <p className="text-xs text-zinc-500 mb-1">Trades</p>
            <p className="text-xl font-bold text-white">{s.num_trades ?? 'N/A'}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-8 bg-zinc-900 border border-zinc-800 rounded-xl p-6">
      <p className="text-green-400 font-semibold">Analysis complete.</p>
      <pre className="text-zinc-400 text-xs mt-2 overflow-x-auto">{JSON.stringify(result, null, 2)}</pre>
    </div>
  )
}

export default function CSVUpload() {
  const [file, setFile] = useState(null)
  const [pastedText, setPastedText] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)

  function clearState() {
    setError('')
    setResult(null)
  }

  function applyFile(selected) {
    if (!selected) return
    const isCSV = selected.name.endsWith('.csv') || selected.type === 'text/csv'
    if (!isCSV) {
      setError('Only .csv files are supported.')
      return
    }
    if (selected.size > 5 * 1024 * 1024) {
      setError('File must be under 5 MB.')
      return
    }
    clearState()
    setPastedText('')
    setFile(selected)
  }

  function handleDragOver(e) {
    e.preventDefault()
    setIsDragging(true)
  }

  function handleDragLeave() {
    setIsDragging(false)
  }

  function handleDrop(e) {
    e.preventDefault()
    setIsDragging(false)
    applyFile(e.dataTransfer.files[0])
  }

  function handleFileChange(e) {
    applyFile(e.target.files[0])
  }

  function handleTextChange(e) {
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''
    clearState()
    setPastedText(e.target.value)
  }

  async function handleAnalyze() {
    clearState()

    let uploadFile = file
    if (!uploadFile && pastedText.trim()) {
      uploadFile = new File([pastedText.trim()], 'pasted.csv', { type: 'text/csv' })
    }
    if (!uploadFile) {
      setError('Please upload a CSV file or paste trade data.')
      return
    }

    setLoading(true)
    const formData = new FormData()
    formData.append('file', uploadFile)
    try {
      const { data } = await axios.post(`${API_URL}/analyze-trades`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to process CSV.')
    } finally {
      setLoading(false)
    }
  }

  const hasInput = file !== null || pastedText.trim().length > 0

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white px-4 py-12">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-white mb-2">Upload Your Trades</h1>
          <p className="text-zinc-400">Upload a CSV file or paste your trade data to get started</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Upload panel */}
          <div className="flex flex-col gap-4">
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-12 cursor-pointer transition-colors ${
                isDragging
                  ? 'border-zinc-400 bg-zinc-800'
                  : 'border-zinc-700 bg-zinc-900 hover:bg-zinc-800'
              }`}
            >
              <UploadCloud className="w-12 h-12 text-zinc-400 mb-3" />
              <p className="text-white font-medium">
                {file ? file.name : 'Drag & drop your CSV here'}
              </p>
              <p className="text-zinc-500 text-sm mt-1">or click to browse files</p>
              <input
                ref={inputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-zinc-400 text-sm">Or paste your trade data:</label>
              <textarea
                value={pastedText}
                onChange={handleTextChange}
                placeholder="Paste CSV data here..."
                className="w-full h-32 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-zinc-300 placeholder-zinc-600 text-sm resize-none focus:outline-none focus:border-zinc-500"
              />
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}

            <button
              onClick={handleAnalyze}
              disabled={loading || !hasInput}
              className="w-full py-3 rounded-xl bg-zinc-700 hover:bg-zinc-600 text-white font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? 'Analyzing...' : 'Analyze Trades'}
            </button>
          </div>

          {/* Format info panel */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-zinc-400" />
              <h2 className="text-white font-semibold">Required CSV Format</h2>
            </div>
            <pre className="bg-zinc-800 rounded-lg px-4 py-3 text-sm text-zinc-300 whitespace-pre overflow-x-auto font-mono">
              {FORMAT_EXAMPLE}
            </pre>
            <div>
              <p className="text-zinc-400 text-sm font-medium mb-2">Column descriptions:</p>
              <ul className="space-y-1">
                {COLUMNS.map(({ name, desc }) => (
                  <li key={name} className="text-sm">
                    <span className="text-white font-medium">{name}:</span>{' '}
                    <span className="text-zinc-400">{desc}</span>
                  </li>
                ))}
              </ul>
            </div>
            <p className="text-zinc-600 text-xs mt-auto">
              Most broker platforms allow you to export your trade history as a CSV file.
              Look for "Export trades" or "Download history" in your broker's platform.
            </p>
          </div>
        </div>

        {result && <ResultsPanel result={result} />}
      </div>
    </div>
  )
}
