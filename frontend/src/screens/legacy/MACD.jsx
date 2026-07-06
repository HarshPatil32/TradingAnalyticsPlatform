import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, Calendar, DollarSign, Plus, X, Play, Moon, Sun, Info, Check, Settings } from 'lucide-react';
import axios from 'axios';

const MACDTrading = () => {
    // API URL from environment variables with fallback
    const API_URL = import.meta.env.VITE_API_URL || 'https://mytradingbot-project.onrender.com';

    // Debug: Log API URL (only in development)
    if (import.meta.env.DEV) {
        console.log('API_URL:', API_URL);
        console.log('Environment variables:', import.meta.env);
    }

    // State management
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const [fieldErrors, setFieldErrors] = useState({});
    const [myStocks, setMyStocks] = useState([]);
    const [stockInput, setStockInput] = useState('');
    const [initialBalance, setInitialBalance] = useState(100000);
    const [backtestResult, setBacktestResult] = useState(null);
    const [spyFinalBalance, setSpyFinalBalance] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [darkMode, setDarkMode] = useState(false);
    const [showSuccess, setShowSuccess] = useState('');
    const [optimizedParams, setOptimizedParams] = useState(null);
    const [optimizationPerformance, setOptimizationPerformance] = useState(null);
    const [macdParams, setMacdParams] = useState({
        fastPeriod: 12,
        slowPeriod: 26,
        signalPeriod: 9
    });

    // Auto-selection state
    const [timeframe, setTimeframe] = useState('medium');
    const [strategyMode, setStrategyMode] = useState('moderate');
    const [isAutoSelecting, setIsAutoSelecting] = useState(false);
    const [selectedStocksData, setSelectedStocksData] = useState([]);

    // Mock chart data for demonstration
    const [chartData, setChartData] = useState([]);

    useEffect(() => {
        // Apply dark mode
        if (darkMode) {
            document.body.style.backgroundColor = '#0f1419';
            document.body.style.color = '#ffffff';
        } else {
            document.body.style.backgroundColor = '#ffffff';
            document.body.style.color = '#000000';
        }
    }, [darkMode]);

    // Validation functions
    const validateField = (field, value) => {
        const errors = { ...fieldErrors };

        switch (field) {
            case 'startDate':
                if (!value) {
                    errors.startDate = 'Start date is required';
                } else {
                    delete errors.startDate;
                }
                break;
            case 'endDate':
                if (!value) {
                    errors.endDate = 'End date is required';
                } else if (startDate && new Date(value) <= new Date(startDate)) {
                    errors.endDate = 'End date must be after start date';
                } else {
                    delete errors.endDate;
                }
                break;
            case 'initialBalance':
                if (!value || isNaN(value) || Number(value) <= 0) {
                    errors.initialBalance = 'Please enter a valid amount greater than 0';
                } else {
                    delete errors.initialBalance;
                }
                break;
            case 'stocks':
                if (value.length === 0) {
                    errors.stocks = 'Please add at least one stock';
                } else {
                    delete errors.stocks;
                }
                break;
        }

        setFieldErrors(errors);
    };

    const isFormValid = () => {
        return startDate && endDate && initialBalance > 0 &&
               new Date(endDate) > new Date(startDate) &&
               Object.keys(fieldErrors).length === 0;
    };

    const isBacktestValid = () => {
        return isFormValid() && myStocks.length > 0;
    };

    // Event handlers
    const handleStartDateChange = (e) => {
        setStartDate(e.target.value);
        validateField('startDate', e.target.value);
        if (endDate) validateField('endDate', endDate);
    };

    const handleEndDateChange = (e) => {
        setEndDate(e.target.value);
        validateField('endDate', e.target.value);
    };

    const handleInitialBalanceChange = (e) => {
        setInitialBalance(e.target.value);
        validateField('initialBalance', e.target.value);
    };

    const handleStockInputChange = (e) => {
        setStockInput(e.target.value.toUpperCase());
    };

    const showSuccessMessage = (message) => {
        setShowSuccess(message);
        setTimeout(() => setShowSuccess(''), 3000);
    };

    const addStock = () => {
        const trimmed = stockInput.trim().toUpperCase();
        if (trimmed && !myStocks.includes(trimmed)) {
            setMyStocks([...myStocks, trimmed]);
            setStockInput('');
            setErrorMessage('');

            // Clear auto-selected data when manual stock is added
            if (selectedStocksData.length > 0) {
                setSelectedStocksData([]);
            }

            validateField('stocks', [...myStocks, trimmed]);
            showSuccessMessage(`${trimmed} added successfully!`);
        } else if (myStocks.includes(trimmed)) {
            setErrorMessage('Stock already added.');
        }
    };

    const deleteStock = (index) => {
        const stockToDelete = myStocks[index];
        const updatedStocks = myStocks.filter((_, i) => i !== index);
        setMyStocks(updatedStocks);

        // Also remove from selected stocks data if it was auto-selected
        const updatedStocksData = selectedStocksData.filter(s => s.symbol !== stockToDelete);
        setSelectedStocksData(updatedStocksData);

        validateField('stocks', updatedStocks);
        showSuccessMessage(`${stockToDelete} removed`);
    };

    const setDateRange = (range) => {
        const endDate = new Date();
        const startDate = new Date();

        switch (range) {
            case '1Y':
                startDate.setFullYear(endDate.getFullYear() - 1);
                break;
            case 'YTD':
                startDate.setMonth(0, 1);
                break;
            case '5Y':
                startDate.setFullYear(endDate.getFullYear() - 5);
                break;
        }

        setStartDate(startDate.toISOString().split('T')[0]);
        setEndDate(endDate.toISOString().split('T')[0]);
        validateField('startDate', startDate.toISOString().split('T')[0]);
        validateField('endDate', endDate.toISOString().split('T')[0]);
    };

    const runBacktest = async () => {
        if (!isBacktestValid()) {
            setErrorMessage('Please ensure all fields are valid and at least one stock is selected.');
            return;
        }

        setIsLoading(true);
        setErrorMessage('');

        try {
            // Call both MACD strategy and SPY investment in parallel with timeout
            const [macdResponse, spyResponse] = await Promise.all([
                axios.get(`${API_URL}/MACD-strategy`, {
                    params: {
                        stocks: myStocks.join(','),
                        start_date: startDate,
                        end_date: endDate,
                        initial_balance: initialBalance,
                        optimize: 'true'
                    },
                    timeout: 120000 // 2 minutes timeout for optimization
                }),
                axios.get(`${API_URL}/spy-investment`, {
                    params: {
                        start_date: startDate,
                        end_date: endDate,
                        initial_balance: initialBalance
                    },
                    timeout: 30000 // 30 seconds timeout for SPY data
                })
            ]);

            // Handle MACD response
            if (macdResponse.data.error) {
                setErrorMessage(macdResponse.data.error);
                return;
            }

            // Handle SPY response
            if (spyResponse.data.error) {
                setErrorMessage(spyResponse.data.error);
                return;
            }

            // Set the optimized parameters
            if (macdResponse.data.optimized_parameters) {
                setOptimizedParams(macdResponse.data.optimized_parameters);
                setOptimizationPerformance(macdResponse.data.optimization_performance);
                setMacdParams({
                    fastPeriod: macdResponse.data.optimized_parameters.fastperiod,
                    slowPeriod: macdResponse.data.optimized_parameters.slowperiod,
                    signalPeriod: macdResponse.data.optimized_parameters.signalperiod
                });
            }

            // Set backtest result
            const backtestResult = macdResponse.data.backtest_result || macdResponse.data;
            setBacktestResult(backtestResult);

            // Set SPY final balance
            setSpyFinalBalance(spyResponse.data.final_balance);

            // Use real monthly performance data from backend
            const generateChartData = () => {
                const macdMonthlyData = macdResponse.data.monthly_performance;
                const spyMonthlyData = spyResponse.data.monthly_performance;

                if (macdMonthlyData && spyMonthlyData) {
                    // Combine both datasets for chart
                    const maxLength = Math.max(macdMonthlyData.length, spyMonthlyData.length);
                    const chartData = [];

                    for (let i = 0; i < maxLength; i++) {
                        const macdPoint = macdMonthlyData[i] || macdMonthlyData[macdMonthlyData.length - 1];
                        const spyPoint = spyMonthlyData[i] || spyMonthlyData[spyMonthlyData.length - 1];

                        chartData.push({
                            month: macdPoint.month,
                            MACD: Math.round(macdPoint.balance),
                            SPY: Math.round(spyPoint.balance)
                        });
                    }

                    return chartData;
                } else {
                    // Fallback to simple calculation if no monthly data
                    const optimizationPerf = macdResponse.data.optimization_performance;
                    if (optimizationPerf && spyResponse.data.final_balance) {
                        const dataPoints = 12;
                        const chartData = [];
                        const macdFinalBalance = optimizationPerf.best_balance;
                        const spyFinalBalance = spyResponse.data.final_balance;

                        const macdTotalReturn = (macdFinalBalance - initialBalance) / initialBalance;
                        const spyTotalReturn = (spyFinalBalance - initialBalance) / initialBalance;

                        const macdMonthlyReturn = Math.pow(1 + macdTotalReturn, 1/dataPoints) - 1;
                        const spyMonthlyReturn = Math.pow(1 + spyTotalReturn, 1/dataPoints) - 1;

                        let macdBalance = initialBalance;
                        let spyBalance = initialBalance;

                        for (let i = 0; i <= dataPoints; i++) {
                            chartData.push({
                                month: i === 0 ? 'Start' : `Month ${i}`,
                                MACD: Math.round(macdBalance),
                                SPY: Math.round(spyBalance)
                            });

                            if (i < dataPoints) {
                                macdBalance *= (1 + macdMonthlyReturn);
                                spyBalance *= (1 + spyMonthlyReturn);

                                macdBalance = Math.max(macdBalance, initialBalance * 0.5);
                                spyBalance = Math.max(spyBalance, initialBalance * 0.5);
                            }
                        }

                        // Adjust final values to match actual results
                        chartData[chartData.length - 1].MACD = Math.round(macdFinalBalance);
                        chartData[chartData.length - 1].SPY = Math.round(spyFinalBalance);

                        return chartData;
                    } else {
                        // Ultimate fallback
                        return [{
                            month: 'Start',
                            MACD: initialBalance,
                            SPY: initialBalance
                        }];
                    }
                }
            };

            setChartData(generateChartData());
            showSuccessMessage('MACD optimization completed and compared with SPY performance!');
        } catch (error) {
            console.error('Error fetching MACD data:', error);
            if (error.response) {
                const status = error.response.status;
                const errorMsg = error.response.data?.error || 'Unknown server error';
                if (status >= 500) {
                    setErrorMessage(`Server error (${status}): ${errorMsg}. The backend may be starting up, please try again in a moment.`);
                } else {
                    setErrorMessage(`Request error (${status}): ${errorMsg}`);
                }
            } else if (error.request) {
                setErrorMessage(`Unable to connect to backend server at ${API_URL}. Please check if the backend is running and try again.`);
            } else {
                setErrorMessage(`Network error: ${error.message}`);
            }
        } finally {
            setIsLoading(false);
        }
    };

    // Auto-selection functionality
    const autoSelectStocks = async () => {
        setIsAutoSelecting(true);
        setErrorMessage('');

        // Set date range based on selected timeframe
        const end = new Date();
        const start = new Date();

        switch (timeframe) {
            case 'short':
                // Short-term: 1-3 months, let's use 3 months
                start.setMonth(end.getMonth() - 3);
                break;
            case 'medium':
                // Medium-term: 3-12 months, let's use 1 year
                start.setFullYear(end.getFullYear() - 1);
                break;
            case 'long':
                // Long-term: 1+ years, let's use 3 years
                start.setFullYear(end.getFullYear() - 3);
                break;
            default:
                start.setFullYear(end.getFullYear() - 1);
        }

        const startDateStr = start.toISOString().split('T')[0];
        const endDateStr = end.toISOString().split('T')[0];

        setStartDate(startDateStr);
        setEndDate(endDateStr);
        validateField('startDate', startDateStr);
        validateField('endDate', endDateStr);

        // Ensure initial balance is set
        if (!initialBalance || initialBalance <= 0) {
            setInitialBalance(100000);
            validateField('initialBalance', 100000);
        }

        try {
            console.log(`Auto-selecting stocks for ${timeframe} timeframe (${startDateStr} to ${endDateStr})...`);

            const response = await axios.get(`${API_URL}/get-optimal-stocks`, {
                params: {
                    timeframe: timeframe,
                    max_stocks: 8,
                    strategy_mode: strategyMode
                },
                timeout: 60000 // 1 minute timeout
            });

            if (response.data.error && response.data.fallback_stocks) {
                // Use fallback stocks if screening failed
                setMyStocks(response.data.fallback_stocks.slice(0, 6));
                setSelectedStocksData([]);
                showSuccessMessage(`Using fallback stocks due to screening limitations`);
            } else if (response.data.selected_stocks) {
                // Use auto-selected stocks
                const stocks = response.data.selected_stocks;
                const stockSymbols = stocks.map(stock => stock.symbol);

                setMyStocks(stockSymbols);
                setSelectedStocksData(stocks);
                validateField('stocks', stockSymbols);

                const timeframeLabel = timeframe === 'short' ? '3-month' : timeframe === 'medium' ? '1-year' : '3-year';
                showSuccessMessage(`Auto-selected ${stocks.length} optimal stocks for ${timeframeLabel} ${timeframe}-term strategy!`);
                console.log('Selected stocks:', stocks);
            } else {
                setErrorMessage('No stocks could be selected. Please try manual selection.');
            }

        } catch (error) {
            console.error('Auto-selection error:', error);
            if (error.response) {
                const status = error.response.status;
                const errorMsg = error.response.data?.error || 'Unknown server error';
                setErrorMessage(`Auto-selection failed (${status}): ${errorMsg}`);
            } else if (error.request) {
                setErrorMessage(`Unable to connect to backend server for stock selection. Please try manual selection.`);
            } else {
                setErrorMessage(`Auto-selection error: ${error.message}`);
            }
        } finally {
            setIsAutoSelecting(false);
        }
    };

    const runAutoTrade = async () => {
        if (!startDate || !endDate) {
            const end = new Date();
            const start = new Date();

            switch (timeframe) {
                case 'short':
                    start.setMonth(end.getMonth() - 3);
                    break;
                case 'medium':
                    start.setFullYear(end.getFullYear() - 1);
                    break;
                case 'long':
                    start.setFullYear(end.getFullYear() - 3);
                    break;
                default:
                    start.setFullYear(end.getFullYear() - 1);
            }

            const startDateStr = start.toISOString().split('T')[0];
            const endDateStr = end.toISOString().split('T')[0];

            setStartDate(startDateStr);
            setEndDate(endDateStr);
            validateField('startDate', startDateStr);
            validateField('endDate', endDateStr);
        }

        if (!initialBalance || initialBalance <= 0) {
            setInitialBalance(100000);
            validateField('initialBalance', 100000);
        }

        if (!isFormValid()) {
            setErrorMessage('Please ensure all fields are valid before running auto-trade.');
            return;
        }

        setIsLoading(true);
        setErrorMessage('');

        try {
            console.log(`Running auto-trade for ${timeframe} timeframe with ${strategyMode} strategy...`);

            const response = await axios.get(`${API_URL}/auto-trade`, {
                params: {
                    timeframe: timeframe,
                    strategy_mode: strategyMode,
                    max_stocks: 5,
                    start_date: startDate,
                    end_date: endDate,
                    initial_balance: initialBalance
                },
                timeout: 180000
            });

            if (response.data.error) {
                setErrorMessage(response.data.error);
                return;
            }

            const autoSelection = response.data.auto_selection;
            if (autoSelection && autoSelection.selected_stocks) {
                const stocks = autoSelection.selected_stocks;
                const stockSymbols = stocks.map(stock => stock.symbol);

                setMyStocks(stockSymbols);
                setSelectedStocksData(stocks);
                validateField('stocks', stockSymbols);
            }

            // Process trading results
            const tradingResults = response.data.trading_results;
            if (tradingResults) {
                setBacktestResult(tradingResults.backtest_result);


                if (tradingResults.optimized_parameters) {
                    setOptimizedParams(tradingResults.optimized_parameters);
                    setMacdParams({
                        fastPeriod: tradingResults.optimized_parameters.fastperiod,
                        slowPeriod: tradingResults.optimized_parameters.slowperiod,
                        signalPeriod: tradingResults.optimized_parameters.signalperiod
                    });

                    // Set optimization performance
                    setOptimizationPerformance({
                        best_balance: tradingResults.final_balance,
                        total_return: tradingResults.total_return_percent
                    });
                }

                // Generate chart data from monthly performance
                if (tradingResults.monthly_performance) {
                    // Also get SPY data for comparison
                    try {
                        const spyResponse = await axios.get(`${API_URL}/spy-investment`, {
                            params: {
                                start_date: startDate,
                                end_date: endDate,
                                initial_balance: initialBalance
                            },
                            timeout: 30000
                        });

                        if (spyResponse.data.final_balance) {
                            setSpyFinalBalance(spyResponse.data.final_balance);

                            // Combine both datasets for chart
                            const macdMonthlyData = tradingResults.monthly_performance;
                            const spyMonthlyData = spyResponse.data.monthly_performance;

                            if (macdMonthlyData && spyMonthlyData) {
                                const maxLength = Math.max(macdMonthlyData.length, spyMonthlyData.length);
                                const combinedChartData = [];

                                for (let i = 0; i < maxLength; i++) {
                                    const macdPoint = macdMonthlyData[i] || macdMonthlyData[macdMonthlyData.length - 1];
                                    const spyPoint = spyMonthlyData[i] || spyMonthlyData[spyMonthlyData.length - 1];

                                    combinedChartData.push({
                                        month: macdPoint.month,
                                        MACD: Math.round(macdPoint.balance),
                                        SPY: Math.round(spyPoint.balance)
                                    });
                                }

                                setChartData(combinedChartData);
                            }
                        }
                    } catch (spyError) {
                        console.warn('Could not fetch SPY data for comparison:', spyError);

                        const macdChartData = tradingResults.monthly_performance.map(point => ({
                            month: point.month,
                            MACD: Math.round(point.balance),
                            SPY: initialBalance // Fallback flat line
                        }));
                        setChartData(macdChartData);
                    }
                }
            }

            showSuccessMessage(`Auto-trading complete! Selected ${autoSelection.selected_stocks.length} stocks and executed strategy with ${tradingResults.total_return_percent.toFixed(2)}% return!`);

        } catch (error) {
            console.error('Auto-trading error:', error);
            if (error.response) {
                const status = error.response.status;
                const errorMsg = error.response.data?.error || 'Unknown server error';
                if (status >= 500) {
                    setErrorMessage(`Server error (${status}): ${errorMsg}. The backend may be starting up, please try again in a moment.`);
                } else {
                    setErrorMessage(`Auto-trading error (${status}): ${errorMsg}`);
                }
            } else if (error.request) {
                setErrorMessage(`Unable to connect to backend server for auto-trading. Please check if the backend is running.`);
            } else {
                setErrorMessage(`Auto-trading error: ${error.message}`);
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className={`min-h-screen transition-colors duration-300 ${
            darkMode ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'
        }`}>
            <div className="container mx-auto px-4 py-8 max-w-6xl">
                {/* Header */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-bold flex items-center gap-3">
                            <TrendingUp className="text-blue-500" size={40} />
                            MACD Trading Strategy
                        </h1>
                        <p className={`mt-2 text-lg ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                            Backtest MACD-based trading strategies and compare against SPY performance
                        </p>
                    </div>
                    <button
                        onClick={() => setDarkMode(!darkMode)}
                        className={`p-3 rounded-lg border transition-colors ${
                            darkMode
                                ? 'bg-gray-800 border-gray-700 hover:bg-gray-700'
                                : 'bg-white border-gray-300 hover:bg-gray-50'
                        }`}
                    >
                        {darkMode ? <Sun size={20} /> : <Moon size={20} />}
                    </button>
                </div>

                {/* Success Toast */}
                {showSuccess && (
                    <div className="mb-4 p-4 bg-green-100 border border-green-300 text-green-800 rounded-lg flex items-center gap-2">
                        <Check size={20} />
                        {showSuccess}
                    </div>
                )}

                {/* Error Message */}
                {errorMessage && (
                    <div className="mb-4 p-4 bg-red-100 border border-red-300 text-red-800 rounded-lg">
                        {errorMessage}
                    </div>
                )}

                <div className="grid lg:grid-cols-2 gap-8">
                    {/* Left Column - Configuration */}
                    <div className="space-y-6">
                        {/* Date Range Section */}
                        <div className={`p-6 rounded-xl border ${
                            darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                        } shadow-lg`}>
                            <div className="flex items-center gap-3 mb-4">
                                <Calendar className="text-blue-500" size={24} />
                                <h2 className="text-xl font-semibold">Date Range</h2>
                            </div>

                            {/* Preset buttons */}
                            <div className="flex flex-wrap gap-2 mb-4">
                                {['1Y', 'YTD', '5Y'].map(range => (
                                    <button
                                        key={range}
                                        onClick={() => setDateRange(range)}
                                        className="px-3 py-1 text-sm bg-blue-100 text-blue-800 rounded-full hover:bg-blue-200 transition-colors"
                                    >
                                        {range}
                                    </button>
                                ))}
                            </div>

                            <div className="grid sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium mb-2">Start Date</label>
                                    <input
                                        type="date"
                                        value={startDate}
                                        onChange={handleStartDateChange}
                                        className={`w-full p-3 border rounded-lg transition-colors ${
                                            darkMode
                                                ? 'bg-gray-700 border-gray-600 focus:border-blue-500'
                                                : 'bg-white border-gray-300 focus:border-blue-500'
                                        } ${fieldErrors.startDate ? 'border-red-500' : ''}`}
                                    />
                                    {fieldErrors.startDate && (
                                        <p className="text-red-500 text-sm mt-1">{fieldErrors.startDate}</p>
                                    )}
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-2">End Date</label>
                                    <input
                                        type="date"
                                        value={endDate}
                                        onChange={handleEndDateChange}
                                        className={`w-full p-3 border rounded-lg transition-colors ${
                                            darkMode
                                                ? 'bg-gray-700 border-gray-600 focus:border-blue-500'
                                                : 'bg-white border-gray-300 focus:border-blue-500'
                                        } ${fieldErrors.endDate ? 'border-red-500' : ''}`}
                                    />
                                    {fieldErrors.endDate && (
                                        <p className="text-red-500 text-sm mt-1">{fieldErrors.endDate}</p>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Investment Amount Section */}
                        <div className={`p-6 rounded-xl border ${
                            darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                        } shadow-lg`}>
                            <div className="flex items-center gap-3 mb-4">
                                <DollarSign className="text-green-500" size={24} />
                                <h2 className="text-xl font-semibold">Investment Amount</h2>
                                <div className="group relative">
                                    <Info size={16} className="text-gray-400 cursor-help" />
                                    <div className="absolute bottom-6 left-0 hidden group-hover:block bg-black text-white text-xs p-2 rounded whitespace-nowrap">
                                        Used for both MACD strategy and SPY comparison
                                    </div>
                                </div>
                            </div>

                            <input
                                type="number"
                                value={initialBalance}
                                onChange={handleInitialBalanceChange}
                                placeholder="e.g., 100000"
                                className={`w-full p-3 border rounded-lg transition-colors ${
                                    darkMode
                                        ? 'bg-gray-700 border-gray-600 focus:border-blue-500'
                                        : 'bg-white border-gray-300 focus:border-blue-500'
                                } ${fieldErrors.initialBalance ? 'border-red-500' : ''}`}
                            />
                            {fieldErrors.initialBalance && (
                                <p className="text-red-500 text-sm">{fieldErrors.initialBalance}</p>
                            )}
                        </div>

                        {/* MACD Parameters */}
                        <div className={`p-6 rounded-xl border ${
                            darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                        } shadow-lg`}>
                            <div className="flex items-center gap-3 mb-4">
                                <Settings className="text-purple-500" size={24} />
                                <h3 className="text-lg font-semibold">MACD Parameters</h3>
                                <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                                    Auto-Optimized
                                </span>
                            </div>

                            <div className={`p-4 rounded-lg border-l-4 border-blue-500 ${
                                darkMode ? 'bg-gray-700' : 'bg-blue-50'
                            }`}>
                                <h4 className="font-semibold text-blue-600 mb-2">
                                    {optimizedParams ? 'Optimized Parameters' : 'Default Parameters (Will be optimized on backtest)'}
                                </h4>
                                <div className="grid grid-cols-3 gap-4 text-sm">
                                    <div>
                                        <span className="font-medium">Fast Period:</span>
                                        <div className="text-lg font-bold text-blue-600">
                                            {optimizedParams ? optimizedParams.fastperiod : macdParams.fastPeriod}
                                        </div>
                                    </div>
                                    <div>
                                        <span className="font-medium">Slow Period:</span>
                                        <div className="text-lg font-bold text-blue-600">
                                            {optimizedParams ? optimizedParams.slowperiod : macdParams.slowPeriod}
                                        </div>
                                    </div>
                                    <div>
                                        <span className="font-medium">Signal Period:</span>
                                        <div className="text-lg font-bold text-blue-600">
                                            {optimizedParams ? optimizedParams.signalperiod : macdParams.signalPeriod}
                                        </div>
                                    </div>
                                </div>
                                <p className="text-xs text-gray-600 mt-2">
                                    Parameters are automatically optimized using Bayesian optimization to maximize returns
                                </p>
                            </div>
                        </div>

                        {/* Stock Selection Section */}
                        <div className={`p-6 rounded-xl border ${
                            darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                        } shadow-lg`}>
                            <h2 className="text-xl font-semibold mb-4">Stock Selection</h2>

                            {/* Auto-Selection Controls */}
                            <div className={`p-4 rounded-lg mb-4 ${
                                darkMode ? 'bg-gray-700' : 'bg-blue-50'
                            }`}>
                                <h3 className="font-semibold text-blue-600 mb-3">Auto-Select Optimal Stocks</h3>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                                    <div>
                                        <label className="block text-sm font-medium mb-2">Trading Timeframe</label>
                                        <select
                                            value={timeframe}
                                            onChange={(e) => setTimeframe(e.target.value)}
                                            className={`w-full p-2 border rounded-lg ${
                                                darkMode
                                                    ? 'bg-gray-600 border-gray-500 text-white'
                                                    : 'bg-white border-gray-300'
                                            }`}
                                        >
                                            <option value="short">Short-term (1-3 months)</option>
                                            <option value="medium">Medium-term (3-12 months)</option>
                                            <option value="long">Long-term (1+ years)</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium mb-2">Strategy Mode</label>
                                        <select
                                            value={strategyMode}
                                            onChange={(e) => setStrategyMode(e.target.value)}
                                            className={`w-full p-2 border rounded-lg ${
                                                darkMode
                                                    ? 'bg-gray-600 border-gray-500 text-white'
                                                    : 'bg-white border-gray-300'
                                            }`}
                                        >
                                            <option value="conservative">Conservative</option>
                                            <option value="moderate">Moderate</option>
                                            <option value="aggressive">Aggressive</option>
                                        </select>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <button
                                        onClick={autoSelectStocks}
                                        disabled={isAutoSelecting}
                                        className={`p-3 rounded-lg font-semibold transition-all flex items-center justify-center gap-2 ${
                                            isAutoSelecting
                                                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                                : 'bg-gradient-to-r from-green-500 to-blue-500 text-white hover:from-green-600 hover:to-blue-600 transform hover:scale-105'
                                        }`}
                                    >
                                        {isAutoSelecting ? (
                                            <>
                                                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                                                <span>Selecting...</span>
                                            </>
                                        ) : (
                                            <>
                                                <TrendingUp size={20} />
                                                <span>Select Stocks</span>
                                            </>
                                        )}
                                    </button>

                                    <button
                                        onClick={runAutoTrade}
                                        disabled={!isFormValid() || isLoading}
                                        className={`p-3 rounded-lg font-semibold transition-all flex items-center justify-center gap-2 ${
                                            !isFormValid() || isLoading
                                                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                                : 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 transform hover:scale-105'
                                        }`}
                                    >
                                        {isLoading ? (
                                            <>
                                                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                                                <span>Auto-Trading...</span>
                                            </>
                                        ) : (
                                            <>
                                                <Play size={20} />
                                                <span>Auto-Trade</span>
                                            </>
                                        )}
                                    </button>
                                </div>

                                <div className="text-xs text-center mt-2 space-y-1">
                                    <div className={darkMode ? 'text-gray-400' : 'text-gray-600'}>
                                        <strong>Select Stocks:</strong> Only find optimal stocks for manual backtesting
                                    </div>
                                    <div className={darkMode ? 'text-gray-400' : 'text-gray-600'}>
                                        <strong>Auto-Trade:</strong> Complete workflow - select stocks + execute strategy + compare with SPY
                                    </div>
                                </div>
                            </div>

                            {/* Manual Stock Input */}
                            <div className="border-t pt-4">
                                <h3 className="font-medium mb-3">Or Add Stocks Manually</h3>
                                <div className="flex gap-2 mb-4">
                                    <input
                                        type="text"
                                        value={stockInput}
                                        onChange={handleStockInputChange}
                                        placeholder="Enter stock symbol (e.g., AAPL)"
                                        className={`flex-1 p-3 border rounded-lg transition-colors ${
                                            darkMode
                                                ? 'bg-gray-700 border-gray-600 focus:border-blue-500'
                                                : 'bg-white border-gray-300 focus:border-blue-500'
                                        }`}
                                        onKeyPress={(e) => e.key === 'Enter' && addStock()}
                                    />
                                    <button
                                        onClick={addStock}
                                        disabled={!stockInput.trim() || myStocks.includes(stockInput.trim().toUpperCase())}
                                        className={`px-4 py-3 rounded-lg font-semibold transition-all flex items-center gap-2 ${
                                            !stockInput.trim() || myStocks.includes(stockInput.trim().toUpperCase())
                                                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                                : 'bg-blue-500 text-white hover:bg-blue-600 transform hover:scale-105'
                                        }`}
                                    >
                                        <Plus size={20} />
                                        Add
                                    </button>
                                </div>
                            </div>

                            {/* Selected Stocks Display */}
                            <div className="mb-4">
                                {myStocks.length > 0 && (
                                    <div className="mb-2">
                                        <h3 className="font-medium text-sm mb-2">
                                            Selected Stocks ({myStocks.length})
                                            {selectedStocksData.length > 0 && <span className="text-green-600 ml-1">Auto-selected</span>}
                                        </h3>
                                    </div>
                                )}

                                <div className="flex flex-wrap gap-2">
                                    {myStocks.map((stock, idx) => {
                                        const stockData = selectedStocksData.find(s => s.symbol === stock);
                                        return (
                                            <div
                                                key={idx}
                                                className={`inline-flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium transition-all hover:bg-blue-200 ${
                                                    stockData
                                                        ? 'bg-green-100 text-green-800 border border-green-200'
                                                        : 'bg-blue-100 text-blue-800'
                                                }`}
                                                title={stockData ? `Score: ${stockData.score?.toFixed(1)} - ${stockData.reason}` : stock}
                                            >
                                                <span className="font-semibold">{stock}</span>
                                                {stockData && (
                                                    <span className="text-xs bg-green-200 text-green-700 px-1 rounded">
                                                        {stockData.score?.toFixed(0)}
                                                    </span>
                                                )}
                                                <button
                                                    onClick={() => deleteStock(idx)}
                                                    className="hover:bg-red-200 rounded-full p-1 transition-colors"
                                                >
                                                    <X size={14} />
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* Show reasoning for auto-selected stocks */}
                                {selectedStocksData.length > 0 && (
                                    <div className={`mt-3 p-3 rounded-lg text-sm ${
                                        darkMode ? 'bg-gray-700 text-gray-300' : 'bg-gray-50 text-gray-600'
                                    }`}>
                                        <div className="font-medium mb-2">Selection Reasoning:</div>
                                        <div className="space-y-1">
                                            {selectedStocksData.map((stock, idx) => (
                                                <div key={idx} className="flex justify-between">
                                                    <span className="font-medium">{stock.symbol}:</span>
                                                    <span className="text-right flex-1 ml-2">{stock.reason}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {fieldErrors.stocks && (
                                <p className="text-red-500 text-sm mb-4">{fieldErrors.stocks}</p>
                            )}

                            <button
                                onClick={runBacktest}
                                disabled={!isBacktestValid() || isLoading}
                                className={`w-full p-4 rounded-lg font-semibold text-lg transition-all flex items-center justify-center gap-3 ${
                                    !isBacktestValid() || isLoading
                                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                        : 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:from-blue-600 hover:to-indigo-700 transform hover:scale-105'
                                }`}
                            >
                                {isLoading ? (
                                    <>
                                        <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
                                        <span className="flex flex-col items-center">
                                            <span>Running Manual Backtest...</span>
                                            <span className="text-xs opacity-80">This may take 1-2 minutes. Backend might be starting up.</span>
                                        </span>
                                    </>
                                ) : (
                                    <>
                                        <Settings size={24} />
                                        <span className="flex flex-col items-center">
                                            <span>Run Manual Backtest</span>
                                            <span className="text-xs opacity-80">Uses your selected stocks with optimization</span>
                                        </span>
                                    </>
                                )}
                            </button>

                            <button
                                onClick={runAutoTrade}
                                disabled={!isFormValid() || isLoading}
                                className={`w-full p-4 rounded-lg font-semibold text-lg transition-all flex items-center justify-center gap-3 mt-4 ${
                                    !isFormValid() || isLoading
                                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                        : 'bg-gradient-to-r from-green-500 to-blue-600 text-white hover:from-green-600 hover:to-blue-700 transform hover:scale-105'
                                }`}
                            >
                                {isLoading ? (
                                    <>
                                        <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
                                        <span className="flex flex-col items-center">
                                            <span>Running Auto-Trade...</span>
                                            <span className="text-xs opacity-80">This may take a few minutes. Backend might be starting up.</span>
                                        </span>
                                    </>
                                ) : (
                                    <>
                                        <Play size={24} />
                                        <span className="flex flex-col items-center">
                                            <span>Run Auto-Trade</span>
                                            <span className="text-xs opacity-80">Auto-selects stocks & executes strategy</span>
                                        </span>
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Right Column - Results */}
                    <div className="space-y-6">
                        {/* Chart Section */}
                        {chartData.length > 0 && (
                            <div className={`p-6 rounded-xl border ${
                                darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                            } shadow-lg`}>
                                <h3 className="text-xl font-semibold mb-4">Performance Comparison</h3>
                                <div className="h-80">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" stroke={darkMode ? '#374151' : '#e5e7eb'} />
                                            <XAxis
                                                dataKey="month"
                                                stroke={darkMode ? '#9ca3af' : '#6b7280'}
                                            />
                                            <YAxis
                                                stroke={darkMode ? '#9ca3af' : '#6b7280'}
                                                tickFormatter={(value) => `$${(value/1000).toFixed(0)}K`}
                                            />
                                            <Tooltip
                                                formatter={(value) => [`$${Number(value).toLocaleString()}`, '']}
                                                contentStyle={{
                                                    backgroundColor: darkMode ? '#1f2937' : '#ffffff',
                                                    border: `1px solid ${darkMode ? '#374151' : '#d1d5db'}`,
                                                    borderRadius: '8px'
                                                }}
                                            />
                                            <Legend />
                                            <Line
                                                type="monotone"
                                                dataKey="MACD"
                                                stroke="#8b5cf6"
                                                strokeWidth={3}
                                                name="MACD Strategy"
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="SPY"
                                                stroke="#10b981"
                                                strokeWidth={3}
                                                name="SPY Buy & Hold"
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        )}

                        {/* Results Section */}
                        {backtestResult && (
                            <div className="space-y-6">
                                {/* Performance Summary */}
                                {spyFinalBalance !== null && (
                                    <div className={`p-6 rounded-xl border ${
                                        darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                                    } shadow-lg`}>
                                        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                            Performance Summary
                                        </h2>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                            {/* MACD Strategy Results */}
                                            <div className={`p-4 rounded-lg border-l-4 border-purple-500 ${
                                                darkMode ? 'bg-gray-700' : 'bg-purple-50'
                                            }`}>
                                                <h3 className="font-semibold text-purple-600 mb-2">MACD Strategy (Optimized)</h3>
                                                <div className="space-y-1 text-sm">
                                                    <div className="flex justify-between">
                                                        <span>Initial Investment:</span>
                                                        <span className="font-semibold">${Number(initialBalance).toLocaleString()}</span>
                                                    </div>
                                                    <div className="flex justify-between">
                                                        <span>Final Balance:</span>
                                                        <span className="font-semibold text-purple-600">
                                                            ${optimizationPerformance ? Number(optimizationPerformance.best_balance).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'N/A'}
                                                        </span>
                                                    </div>
                                                    <div className="flex justify-between">
                                                        <span>Return:</span>
                                                        <span className={`font-semibold ${
                                                            optimizationPerformance && optimizationPerformance.best_balance > initialBalance ? 'text-green-600' : 'text-red-600'
                                                        }`}>
                                                            {optimizationPerformance ?
                                                                optimizationPerformance.total_return.toFixed(2) + '%'
                                                                : 'N/A'}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>

                                            {/* SPY Results */}
                                            <div className={`p-4 rounded-lg border-l-4 border-green-500 ${
                                                darkMode ? 'bg-gray-700' : 'bg-green-50'
                                            }`}>
                                                <h3 className="font-semibold text-green-600 mb-2">SPY Buy & Hold</h3>
                                                <div className="space-y-1 text-sm">
                                                    <div className="flex justify-between">
                                                        <span>Initial Investment:</span>
                                                        <span className="font-semibold">${Number(initialBalance).toLocaleString()}</span>
                                                    </div>
                                                    <div className="flex justify-between">
                                                        <span>Final Balance:</span>
                                                        <span className="font-semibold text-green-600">
                                                            ${Number(spyFinalBalance).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                                        </span>
                                                    </div>
                                                    <div className="flex justify-between">
                                                        <span>Return:</span>
                                                        <span className={`font-semibold ${
                                                            spyFinalBalance > initialBalance ? 'text-green-600' : 'text-red-600'
                                                        }`}>
                                                            {(((spyFinalBalance - initialBalance) / initialBalance) * 100).toFixed(2)}%
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Strategy Comparison */}
                                        {optimizationPerformance && (
                                            <div className={`mt-6 p-4 rounded-lg ${
                                                optimizationPerformance.best_balance > spyFinalBalance
                                                    ? 'bg-green-100 border border-green-300'
                                                    : 'bg-red-100 border border-red-300'
                                            }`}>
                                                <div className="flex items-center justify-between">
                                                    <span className="font-semibold">
                                                        {optimizationPerformance.best_balance > spyFinalBalance
                                                            ? 'MACD Strategy Outperformed SPY!'
                                                            : 'SPY Outperformed MACD Strategy'}
                                                    </span>
                                                    <span className={`font-bold text-lg ${
                                                        optimizationPerformance.best_balance > spyFinalBalance ? 'text-green-600' : 'text-red-600'
                                                    }`}>
                                                        {optimizationPerformance.best_balance > spyFinalBalance ? '+' : ''}
                                                        ${(optimizationPerformance.best_balance - spyFinalBalance).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                                    </span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Detailed Backtest Results */}
                                <div className={`p-6 rounded-xl border ${
                                    darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
                                } shadow-lg`}>
                                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                        Detailed Backtest Results
                                    </h2>
                                    <div
                                        className={`p-4 rounded-lg ${
                                            darkMode ? 'bg-gray-700' : 'bg-gray-50'
                                        }`}
                                        dangerouslySetInnerHTML={{ __html: backtestResult }}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Placeholder when no results */}
                        {!backtestResult && !isLoading && (
                            <div className={`p-8 rounded-xl border-2 border-dashed ${
                                darkMode ? 'border-gray-600 text-gray-400' : 'border-gray-300 text-gray-500'
                            } text-center`}>
                                <TrendingUp size={48} className="mx-auto mb-4 opacity-50" />
                                <p className="text-lg">Configure your strategy and run a backtest to see results here</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MACDTrading;
