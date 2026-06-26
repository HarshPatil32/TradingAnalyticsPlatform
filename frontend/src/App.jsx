import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, Outlet, useNavigate, useLocation } from 'react-router-dom'
import CSVUpload from './screens/CSVUpload'
import TradeReport from './screens/TradeReport'
import Home from './screens/Home'
import heartbeatService from './services/heartbeat'
import { API_URL } from './config'

const navLinkClass = ({ isActive }) =>
  `px-4 py-2 rounded text-sm font-medium transition-colors ${
    isActive ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
  }`

function MainLayout() {
  return (
    <div className="bg-[#0a0a0a] min-h-screen">
      <nav className="flex flex-wrap gap-2 p-4 border-b border-zinc-800 bg-[#0a0a0a]">
        <NavLink to="/" end className={navLinkClass}>Home</NavLink>
        <NavLink to="/upload" className={navLinkClass}>Upload Trades</NavLink>
      </nav>
      <Outlet />
    </div>
  )
}

// Reads result from router location state (fresh upload) or sessionStorage (page refresh)
function TradeReportRoute({ onBack, onUpgrade }) {
  const { state } = useLocation()
  const result = state?.result ?? (() => {
    try { return JSON.parse(sessionStorage.getItem('tradeReport')) ?? null } catch { return null }
  })()
  if (!result) return <Navigate to="/upload" replace />
  // TODO: derive isPro from a verified auth session; enforce Pro features server-side too.
  return (
    <TradeReport
      result={result}
      onBack={onBack}
      isPro={false}
      onUpgrade={onUpgrade}
    />
  )
}

function AppRoutes() {
  const navigate = useNavigate()

  function handleResult(data) {
    try {
      sessionStorage.setItem('tradeReport', JSON.stringify(data))
    } catch {
      // Storage unavailable (e.g. private mode quota) — result still travels via router state
    }
    // Pass data atomically with the navigation — no state/render race condition
    navigate('/report', { state: { result: data } })
  }

  return (
    <Routes>
      <Route path="/" element={<Home onAnalyze={() => navigate('/upload')} />} />
      <Route element={<MainLayout />}>
        <Route path="/upload" element={<CSVUpload onResult={handleResult} />} />
        <Route
          path="/report"
          element={
            <TradeReportRoute
              onBack={() => navigate('/upload')}
              onUpgrade={() => {
                // Placeholder until billing is integrated.
              }}
            />
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  useEffect(() => {
    heartbeatService.setApiUrl(API_URL)
    heartbeatService.start()
    return () => heartbeatService.stop()
  }, [])

  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App