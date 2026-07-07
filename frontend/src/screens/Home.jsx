import { TrendingUp } from 'lucide-react'

const pillars = [
  { title: 'Any Broker', description: 'Upload any CSV format' },
  { title: 'True Returns', description: 'After fees, spreads, and taxes' },
  { title: 'Benchmark', description: 'SPY and QQQ comparison' },
  { title: 'Plain English', description: 'No finance background needed' },
]

export default function Home({ onAnalyze }) {
  return (
    <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center px-4 text-center">
      <div className="flex flex-col items-center gap-6 mb-16">
        <div className="w-20 h-20 bg-zinc-800 rounded-2xl flex items-center justify-center">
          <TrendingUp className="w-9 h-9 text-white" strokeWidth={2} />
        </div>

        <div className="flex flex-col items-center gap-3">
          <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight">
            Trade Analyzer
          </h1>
          <p className="text-lg text-zinc-400">
            Upload your trades. Find out why you&apos;re really winning or losing.
          </p>
        </div>

        <button
          onClick={onAnalyze}
          disabled={!onAnalyze}
          className="mt-2 px-8 py-4 bg-white text-black font-semibold rounded-xl hover:bg-zinc-100 transition-colors duration-150 text-base disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Analyze My Trades
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-8 sm:gap-12">
        {pillars.map(({ title, description }) => (
          <div key={title} className="flex flex-col items-center gap-1">
            <span className="text-2xl font-bold text-white">{title}</span>
            <span className="text-sm text-zinc-500">{description}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
