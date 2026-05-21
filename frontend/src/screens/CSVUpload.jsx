// Upload screen: drag-and-drop or file picker plus paste, then calls /analyze-trades
import { useState, useRef, useEffect } from 'react'
import { UploadCloud, FileText, ChevronDown, Download, Loader2 } from 'lucide-react'
import axios from 'axios'
import { API_URL } from '../config'
import { FORMAT_EXAMPLE, BROKER_STEPS, COLUMNS, validateFile } from './CSVUpload.constants'

export function ResultsPanel({ result }) {
  if (!result || typeof result !== 'object') return null

  const warnings = Array.isArray(result.warnings) ? result.warnings : []
  const notices = Array.isArray(result.notices) ? result.notices : []

  const feedbackSection = (warnings.length > 0 || notices.length > 0) ? (
    <div className="space-y-1 pt-3 border-t border-zinc-800">
      {warnings.map((w, i) => (
        w.message ? <p key={`w${i}`} className="text-yellow-400 text-sm">{w.message}</p> : null
      ))}
      {notices.map((n, i) => (
        n.message ? <p key={`n${i}`} className="text-zinc-400 text-sm">{n.message}</p> : null
      ))}
    </div>
  ) : null

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
        {feedbackSection}
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
        {feedbackSection}
      </div>
    )
  }

  return (
    <div className="mt-8 bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
      <p className="text-green-400 font-semibold">Analysis complete.</p>
      <pre className="text-zinc-400 text-xs mt-2 overflow-x-auto">{JSON.stringify(result, null, 2)}</pre>
      {feedbackSection}
    </div>
  )
}

export default function CSVUpload() {
  const [file, setFile] = useState(null)
  const [pastedText, setPastedText] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [showBrokerGuide, setShowBrokerGuide] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  function clearState() {
    setError('')
    setResult(null)
  }

  function applyFile(selected) {
    if (!selected) return
    const validationError = validateFile(selected)
    if (validationError) {
      setError(validationError)
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
      if (!mountedRef.current) return
      setResult(data)
      setFile(null)
      setPastedText('')
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      if (!mountedRef.current) return
      const data = err.response?.data
      const msg =
        data?.error ||
        data?.message ||
        (Array.isArray(data?.errors) && data.errors[0]?.message) ||
        'Failed to process CSV.'
      setError(msg)
    } finally {
      if (mountedRef.current) setLoading(false)
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
              aria-label={loading ? 'Analyzing trades, please wait' : 'Analyze Trades'}
              className="w-full py-3 rounded-xl bg-zinc-700 hover:bg-zinc-600 text-white font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  Analyzing...
                </span>
              ) : 'Analyze Trades'}
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
            <a
              href="/example-trades.csv"
              download="example-trades.csv"
              aria-label="Download example trades CSV file"
              className="flex items-center gap-2 text-zinc-400 text-sm hover:text-white transition-colors self-start"
            >
              <Download className="w-4 h-4" />
              Download example file
            </a>
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
            <div className="border-t border-zinc-800 pt-4 mt-auto">
              <button
                onClick={() => setShowBrokerGuide(v => !v)}
                className="flex items-center gap-2 text-zinc-400 text-sm hover:text-white transition-colors w-full text-left"
              >
                <ChevronDown className={`w-4 h-4 transition-transform ${showBrokerGuide ? 'rotate-180' : ''}`} />
                How to export from your broker
              </button>
              {showBrokerGuide && (
                <div className="mt-3 space-y-4">
                  {BROKER_STEPS.map(({ name, steps }) => (
                    <div key={name}>
                      <p className="text-white text-sm font-medium mb-1">{name}</p>
                      <ol className="space-y-1 list-decimal pl-4">
                        {steps.map((step) => (
                          <li key={step} className="text-zinc-400 text-xs">{step}</li>
                        ))}
                      </ol>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {result && <ResultsPanel result={result} />}
      </div>
    </div>
  )
}
