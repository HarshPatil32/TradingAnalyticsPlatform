import { useEffect, useState } from 'react'
import MACDTrading from './screens/legacy/MACD'
import CSVUpload from './screens/CSVUpload'
import Home from './screens/Home'
import heartbeatService from './services/heartbeat'
import { API_URL } from './config'

function App() {
  const [activeTab, setActiveTab] = useState('home')

  useEffect(() => {
    heartbeatService.setApiUrl(API_URL);
    heartbeatService.start();
    return () => heartbeatService.stop();
  }, []);

  return (
    <>
      {activeTab === 'home' ? (
        <Home onAnalyze={() => setActiveTab('csvupload')} />
      ) : (
        <div className="app bg-[#0a0a0a] min-h-screen">
          <nav className="flex flex-wrap gap-2 p-4 border-b border-zinc-800 bg-[#0a0a0a]">
            <button
              onClick={() => setActiveTab('home')}
              className="px-4 py-2 rounded text-sm font-medium text-zinc-400 hover:bg-zinc-800 hover:text-white transition-colors"
            >
              Home
            </button>
            <button
              onClick={() => setActiveTab('csvupload')}
              className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                activeTab === 'csvupload' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
              }`}
            >
              Upload Trades
            </button>
            <button
              onClick={() => setActiveTab('macd')}
              className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
                activeTab === 'macd' ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white'
              }`}
            >
              MACD Strategy
            </button>
          </nav>
          <div className="content">
            {activeTab === 'csvupload' && <CSVUpload />}
            {activeTab === 'macd' && <MACDTrading />}
          </div>
        </div>
      )}
    </>
  );
}

export default App