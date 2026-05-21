import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import MACDTrading from './screens/legacy/MACD'
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
        <NavLink to="/macd" className={navLinkClass}>MACD Strategy</NavLink>
      </nav>
      <Outlet />
    </div>
  )
}

function AppRoutes() {
  const navigate = useNavigate()
  const [reportResult, setReportResult] = useState(null)

  function handleResult(data) {
    setReportResult(data)
    navigate('/report')
  }

  return (
    <Routes>
      <Route path="/" element={<Home onAnalyze={() => navigate('/upload')} />} />
      <Route element={<MainLayout />}>
        <Route path="/upload" element={<CSVUpload onResult={handleResult} />} />
        <Route
          path="/report"
          element={
            reportResult
              ? <TradeReport result={reportResult} onBack={() => navigate('/upload')} />
              : <Navigate to="/upload" replace />
          }
        />
        <Route path="/macd" element={<MACDTrading />} />
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