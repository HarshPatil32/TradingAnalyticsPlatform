from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import os
import re
from datetime import datetime, timezone
import requests
import json
import numpy as np
import threading
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from csv_analyzer import analyze_uploaded_trades, FreeTierLimitExceeded

# Load env vars early so they are available at module scope (picked up by gunicorn too)
load_dotenv()

# Configure logging before validation so INFO messages are not swallowed
logging.basicConfig(level=logging.INFO)

# Env vars the app cares about. Add new secrets here as they are introduced.
# required=True  -> WARNING logged on boot if missing
# required=False -> INFO logged on boot if missing (has a safe fallback)
_ENV_VAR_MANIFEST = (
    {"name": "PORT",             "required": False, "description": "Port Flask listens on (defaults to 5001)"},
    {"name": "FLASK_DEBUG",      "required": False, "description": "Enable Flask debug mode"},
    {"name": "ALLOWED_ORIGINS",  "required": False, "description": "Comma-separated CORS origins; defaults to * (all) if not set"},
)


def validate_env_vars():
    """Check for expected env vars and log warnings for any that are missing."""
    missing_required = []
    missing_optional = []

    for var in _ENV_VAR_MANIFEST:
        if not os.environ.get(var["name"]):
            if var["required"]:
                logging.warning("Missing required env var: %s (%s)", var["name"], var["description"])
                missing_required.append(var["name"])
            else:
                logging.info("Optional env var not set: %s (%s)", var["name"], var["description"])
                missing_optional.append(var["name"])

    return {
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "all_present": len(missing_required) == 0,
    }


# Skip during test runs to avoid noisy warnings and protect against future required vars
if not os.getenv("TESTING"):
    ENV_STARTUP_STATUS = validate_env_vars()
else:
    ENV_STARTUP_STATUS = {"missing_required": [], "missing_optional": [], "all_present": True}

# Resolve allowed CORS origins. "*" keeps local dev open; in production set
# ALLOWED_ORIGINS=https://yourdomain.com (comma-separated for multiple).
def _parse_allowed_origins() -> "str | list[str]":
    _logger = logging.getLogger(__name__)
    raw_env = os.getenv("ALLOWED_ORIGINS")

    # Var not set at all — safe default for local dev
    if raw_env is None:
        return "*"

    raw = raw_env.strip()

    if not raw:
        _logger.warning(
            "ALLOWED_ORIGINS is set but empty; falling back to '*'. "
            "Set a real domain in production."
        )
        return "*"

    if raw == "*":
        return "*"

    origins = [o.strip() for o in raw.split(",") if o.strip()]

    for origin in origins:
        if not origin.startswith(("http://", "https://")):
            _logger.warning("ALLOWED_ORIGINS entry looks invalid (expected http/https): %s", origin)

    return origins if origins else "*"


def _build_cors_origins(parsed: "str | list[str]"):
    """Expand parsed ALLOWED_ORIGINS for Flask-CORS (supports Vercel preview deploys)."""
    if parsed == "*":
        return "*"

    cors_origins: list = list(parsed)

    for origin in parsed:
        if origin.startswith(("http://", "https://")) and "*" in origin:
            scheme, rest = origin.split("://", 1)
            regex_body = re.escape(rest).replace(r"\*", ".*")
            cors_origins.append(re.compile(rf"^{scheme}://{regex_body}$"))
            continue

        match = re.match(r"^(https://)([^./]+)\.vercel\.app$", origin)
        if match:
            scheme, slug = match.group(1), match.group(2)
            cors_origins.append(
                re.compile(rf"^{scheme}{re.escape(slug)}(-[a-zA-Z0-9-]+)*\.vercel\.app$")
            )

    return cors_origins


ALLOWED_ORIGINS = _parse_allowed_origins()
CORS_ORIGINS = _build_cors_origins(ALLOWED_ORIGINS)

# Strict policy for a JSON-only API. Expand this if HTML routes are added.
CSP_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'self'"

_MB = 1024 * 1024
# Max upload size for all file uploads (5 MB). Applies to every route via MAX_CONTENT_LENGTH.
# Keep in sync with MAX_FILE_BYTES in frontend/src/screens/BacktestUpload.jsx
_MAX_UPLOAD_BYTES = 5 * _MB

# Free tier: max analyses per IP per calendar month (UTC)
MONTHLY_ANALYSIS_LIMIT = 5

# In-memory store: maps (ip, "YYYY-MM") -> request count.
# Counts reset when the server restarts — users could exceed the monthly cap
# across restarts. Acceptable for the free tier; replace with persistent
# storage (e.g. Redis) if stricter enforcement is needed.
_rate_limit_store: dict[tuple[str, str], int] = {}
_rate_limit_lock = threading.Lock()


def _get_client_ip() -> str:
    """Return the real client IP, honouring X-Forwarded-For set by Render's proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # Use the rightmost entry — added by our trusted proxy, not the client.
        # The leftmost entries can be spoofed by the client.
        return forwarded_for.split(",")[-1].strip()
    return request.remote_addr or "unknown"


def _get_month_key() -> str:
    """Return the current UTC month as 'YYYY-MM'. Extracted so tests can patch it."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP is within the monthly limit, False if exceeded."""
    key = (ip, _get_month_key())
    with _rate_limit_lock:
        count = _rate_limit_store.get(key, 0)
        if count >= MONTHLY_ANALYSIS_LIMIT:
            return False
        _rate_limit_store[key] = count + 1
    return True

# Try to import trading modules with error handling

try:
    from test_against_SP import get_spy_investment, generate_spy_monthly_performance
    from MACD_trading import backtest_strategy_MACD, generate_monthly_performance
    from optimize_MACD import optimize_macd_parameters
    TRADING_MODULES_AVAILABLE = True
except ImportError as e:
    logging.error(f"Trading modules not available: {e}")
    TRADING_MODULES_AVAILABLE = False
    def get_spy_investment(*args, **kwargs):
        raise RuntimeError("Trading modules not available")
    def generate_spy_monthly_performance(*args, **kwargs):
        raise RuntimeError("Trading modules not available")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = _MAX_UPLOAD_BYTES

CORS(app, resources={
    r"/*": {
        "origins": CORS_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

logger = logging.getLogger(__name__)

@app.after_request
def set_security_headers(response):
    response.headers["Content-Security-Policy"] = CSP_POLICY
    return response

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(413)
def request_too_large(error):
    limit_mb = _MAX_UPLOAD_BYTES // _MB
    return jsonify({"error": f"Payload too large. Maximum allowed size is {limit_mb} MB."}), 413

@app.route("/", methods=["GET"])
def health_check():
    resp = {
        "status": "API is running",
        "message": "Flask trading API",
        "env_status": {
            "all_present": ENV_STARTUP_STATUS["all_present"],
            # Only expose missing var names in debug mode to avoid information disclosure
            "missing_required": ENV_STARTUP_STATUS["missing_required"] if app.debug else [],
        },
    }
    return jsonify(resp), 200

@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    """Lightweight heartbeat endpoint to keep server alive"""
    return jsonify({
        "status": "alive", 
        "timestamp": datetime.now().isoformat(),
        "message": "Server is running"
    }), 200


@app.route("/config", methods=["GET"])
def config():
    """Expose server-side limits so clients can stay in sync without hardcoding."""
    return jsonify({
        "max_upload_bytes": _MAX_UPLOAD_BYTES,
    }), 200


@app.route("/webhookcallback", methods=["POST"])
def hook():
    try:
        if request.is_json:
            data = request.get_json()
            logger.info(f"Webhook received: {data}")
            return jsonify({"status": "success", "message": "Webhook received"}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid content type"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/MACD-strategy', methods=['GET'])
def MACD_strategy():
    if not TRADING_MODULES_AVAILABLE:
        return jsonify({"error": "Trading modules not available. Please check server setup."}), 500
    
    try:
        stocks = request.args.get('stocks')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        initial_balance = request.args.get('initial_balance', default=100000, type=int)
        optimize = request.args.get('optimize', default='true').lower() == 'true'
        
        # Validate required parameters
        if not stocks or not start_date_str or not end_date_str:
            return jsonify({"error": "Missing required parameters: stocks, start_date, end_date"}), 400

        stock_list = [stock.strip() for stock in stocks.split(',') if stock.strip()]
        
        try:
            start_date_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError as e:
            return jsonify({"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}"}), 400

        logger.info(f"Processing MACD strategy for stocks: {stock_list}, dates: {start_date_str} to {end_date_str}, optimize: {optimize}")
        
        if optimize:
            # First optimize parameters for the given stocks and dates
            optimization_result = optimize_macd_parameters(
                symbols=stock_list,
                start_date=start_date_dt,
                end_date=end_date_dt,
                initial_balance=initial_balance,
                n_iterations=15  # Reduced for faster response time
            )
            
            optimized_params = optimization_result['optimized_params']
            
            # Run backtest with optimized parameters
            str_result, final_balance = backtest_strategy_MACD(
                stock_list, 
                start_date_dt, 
                end_date_dt, 
                initial_balance,
                fastperiod=optimized_params['fastperiod'],
                slowperiod=optimized_params['slowperiod'],
                signalperiod=optimized_params['signalperiod']
            )
            
            formatted_result = str_result.replace("\n", "<br />")
            
            # Generate monthly performance data for charting
            monthly_data = generate_monthly_performance(
                stock_list,
                start_date_dt,
                end_date_dt,
                initial_balance,
                fastperiod=optimized_params['fastperiod'],
                slowperiod=optimized_params['slowperiod'],
                signalperiod=optimized_params['signalperiod']
            )
            
            # Return both the backtest result and optimized parameters
            return jsonify({
                "backtest_result": formatted_result,
                "optimized_parameters": optimized_params,
                "optimization_performance": {
                    "best_balance": optimization_result['best_balance'],
                    "total_return": optimization_result['total_return']
                },
                "monthly_performance": monthly_data
            }), 200
        else:
            # Run backtest with default parameters (legacy behavior)
            str_result, _ = backtest_strategy_MACD(stock_list, start_date_dt, end_date_dt, initial_balance)
            formatted_result = str_result.replace("\n", "<br />")
            return jsonify({"backtest_result": formatted_result}), 200
            
    except Exception as e:
        logger.error(f"MACD strategy error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/spy-investment', methods=['GET'])
def spy_investment():
    if not TRADING_MODULES_AVAILABLE:
        return jsonify({"error": "Trading modules not available. Please check server setup."}), 500

    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        initial_balance = request.args.get('initial_balance', default=100000, type=int)

        # Validate required parameters
        if not start_date_str or not end_date_str:
            return jsonify({"error": "Missing required parameters: start_date, end_date"}), 400

        try:
            start_date = datetime.fromisoformat(start_date_str)
            end_date = datetime.fromisoformat(end_date_str)
        except (ValueError, TypeError) as e:
            return jsonify({"error": "Invalid date format. Please provide dates in ISO format (YYYY-MM-DD)."}), 400

        logger.info(f"Processing SPY investment for dates: {start_date_str} to {end_date_str}")

        final_balance = get_spy_investment(start_date, end_date, initial_balance)
        # If get_spy_investment returns an error tuple, handle it
        if isinstance(final_balance, tuple) and len(final_balance) == 2 and isinstance(final_balance[1], int):
            error_msg, status = final_balance
            return jsonify({"error": error_msg}), status

        monthly_data = generate_spy_monthly_performance(start_date, end_date, initial_balance)

        return jsonify({
            "final_balance": final_balance,
            "monthly_performance": monthly_data
        }), 200

    except Exception as e:
        logger.error(f"SPY investment error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Expose for patching in tests only if available
import sys
sys.modules[__name__].get_spy_investment = get_spy_investment
sys.modules[__name__].generate_spy_monthly_performance = generate_spy_monthly_performance

def generate_selection_reason(score):
    """Give a reason for why it chose the stock"""
    if score >= 85:
        return "Excellent MACD signals with strong momentum"
    elif score >= 75:
        return "Strong MACD patterns and good volume"
    elif score >= 65:
        return "Good technical setup for MACD strategy"
    elif score >= 55:
        return "Decent MACD potential with acceptable risk"
    else:
        return "Basic MACD suitability"


@app.route('/get-optimal-stocks', methods=['GET'])
def get_optimal_stocks():
    """This route will select the most optimal stocks for you"""
    if not TRADING_MODULES_AVAILABLE:
        return jsonify({"error": "Trading modules not available. Please check server setup"}), 500
    
    try:
        from stock_screener import StockScreener

        # Get the parameters we need
        timeframe = request.args.get('timeframe', default = 'medium')
        max_stocks = request.args.get('max_stocks', default=5, type=int)
        risk = request.args.get('risk', default = 'moderate')

        # Check the timeframe
        valid_timeframes = ['short', 'medium', 'long']
        if timeframe not in valid_timeframes:
            return jsonify({"error": "The timeframe isn't valid, please choose short, medium or long"}), 400
        
        # Cap the max stocks at 10
        if max_stocks < 1 or max_stocks > 10:
            return jsonify({"error": "Please choose a number between 1 and 10 inclusive"})
        
        screener = StockScreener()
        
        try:
            is_deployment = os.environ.get('PORT') is not None
            
            if is_deployment:
                # Use ultra-fast method for deployment
                selected_stocks = screener.screen_stocks_fast_deployment(
                    timeframe=timeframe, 
                    max_stocks=max_stocks
                )
            else:
                # Use full method for local development (temporary, will try to optimize)
                selected_stocks = screener.screen_stocks_for_macd(
                    timeframe=timeframe, 
                    max_stocks=max_stocks, 
                    timeout_seconds=45
                )
        except Exception as screening_error:
            logger.error(f"Stock screening failed: {screening_error}")
            # Return fallback stocks immediately instead of error
            selected_stocks = screener.get_fallback_stocks(max_stocks)
            logger.info("Using fallback stocks due to screening timeout")

        if not selected_stocks:
            return jsonify({"error": "No suitable stocks found with your criteria. Please try different timeframe or risk level settings."}), 400
        
        for stock in selected_stocks:
            stock['reason'] = generate_selection_reason(stock['score'])

        response_data = {
            "selected_stocks": selected_stocks,
            "timeframe": timeframe,
            "risk": risk,
            "total_candidates_screened": int(len(selected_stocks) * 10),  # Rough estimate
            "selection_criteria": f"MACD-optimized for {timeframe}-term trading",
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Stock screening error: {str(e)}")
        return jsonify({
            "error": f"Stock screening failed: {str(e)}. Please check system status and try again."
        }), 500

@app.route('/auto-trade', methods=['GET'])
def auto_trade():
    if not TRADING_MODULES_AVAILABLE:
        return jsonify({"error": "Trading modules not available. Please check server setup"}), 500
    
    try:
        from stock_screener import StockScreener

        # Get parameters
        timeframe = request.args.get('timeframe', default='medium')
        risk = request.args.get('risk', default='moderate')
        max_stocks = request.args.get('max_stocks', default=5, type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')  
        initial_balance = request.args.get('initial_balance', default=100000, type=int)
        
        # Validate parameters
        valid_timeframes = ['short', 'medium', 'long']
        if timeframe not in valid_timeframes:
            return jsonify({"error": "Invalid timeframe. Choose: short, medium, long"}), 400
            
        if max_stocks < 1 or max_stocks > 10:
            return jsonify({"error": "max_stocks must be between 1 and 10"}), 400
            
        if not start_date_str or not end_date_str:
            return jsonify({"error": "Missing required parameters: start_date, end_date"}), 400

        try:
            start_date_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError as e:
            return jsonify({"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}"}), 400

        logger.info(f"Auto-trading: timeframe={timeframe}, risk={risk}, dates={start_date_str} to {end_date_str}")

        # Select optimal stocks with timeout handling
        screener = StockScreener()
        
        try:
            # Check if we're in deployment
            is_deployment = os.environ.get('PORT') is not None
            
            if is_deployment:
                # Always use fast method for auto-trade in deployment
                selected_stocks = screener.screen_stocks_fast_deployment(
                    timeframe=timeframe, 
                    max_stocks=max_stocks
                )
            else:
                # Use full method locally with short timeout
                selected_stocks = screener.screen_stocks_for_macd(
                    timeframe=timeframe, 
                    max_stocks=max_stocks,
                    timeout_seconds=20  # Very short timeout for auto-trade
                )
        except Exception as screening_error:
            logger.error(f"Auto-trade stock screening failed: {screening_error}")
            # Use fallback instead of failing
            selected_stocks = screener.get_fallback_stocks(max_stocks)
            logger.info("Using fallback stocks for auto-trade due to screening timeout")

        if not selected_stocks:
            return jsonify({
                "error": "No suitable stocks found for auto-trading. Please try different timeframe or risk settings."
            }), 400

        # Add reasoning to selected stocks (for me)
        for stock in selected_stocks:
            stock['reason'] = generate_selection_reason(stock['score'])

        # Get the stock symbols for trading
        stock_symbols = [stock['symbol'] for stock in selected_stocks]
        
        # Use the MACD strategy with Bayesian optimization
        optimization_result = optimize_macd_parameters(
            symbols=stock_symbols,
            start_date=start_date_dt,
            end_date=end_date_dt,
            initial_balance=initial_balance,
            n_iterations=15  # Balanced performance vs speed (open to change)
        )
        
        optimized_params = optimization_result['optimized_params']
        
        # Run backtest with optimized parameters
        str_result, final_balance = backtest_strategy_MACD(
            stock_symbols, 
            start_date_dt, 
            end_date_dt, 
            initial_balance,
            fastperiod=optimized_params['fastperiod'],
            slowperiod=optimized_params['slowperiod'],
            signalperiod=optimized_params['signalperiod']
        )
        
        # Generate monthly performance data
        monthly_data = generate_monthly_performance(
            stock_symbols,
            start_date_dt,
            end_date_dt,
            initial_balance,
            fastperiod=optimized_params['fastperiod'],
            slowperiod=optimized_params['slowperiod'],
            signalperiod=optimized_params['signalperiod']
        )

        # Calculate performance metrics
        total_return = ((final_balance - initial_balance) / initial_balance) * 100
        
        # Return comprehensive results
        response_data = {
            "auto_selection": {
                "selected_stocks": selected_stocks,
                "selection_criteria": f"MACD-optimized for {timeframe}-term trading",
                "timeframe": timeframe,
                "risk": risk,
                "total_candidates_screened": len(selected_stocks) * 10  # Rough estimate
            },
            "trading_results": {
                "backtest_result": str_result.replace("\n", "<br />"),
                "initial_balance": initial_balance,
                "final_balance": final_balance,
                "total_return_percent": round(total_return, 2),
                "optimized_parameters": optimized_params,
                "monthly_performance": monthly_data
            },
            "summary": {
                "strategy": "MACD with Bayesian Optimization",
                "period": f"{start_date_str} to {end_date_str}",
                "stocks_traded": stock_symbols,
                "performance": f"{total_return:+.2f}%",
                "risk_level": risk
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Auto-trading error: {str(e)}")
        return jsonify({
            "error": f"Auto-trading failed: {str(e)}",
            "suggestion": "Try with different parameters or check system status"
        }), 500

def _safe_filename(raw: str) -> str:
    """Sanitize an upload filename to prevent path traversal."""
    name = secure_filename(raw)
    if not name:
        # secure_filename strips everything for names like '../../' or all-unicode
        raise ValueError("Filename is invalid or empty after sanitization")
    return name


@app.route('/analyze-trades', methods=['POST'])
def analyze_trades():
    """Accept a CSV upload and return sanitized trade analysis."""

    ip = _get_client_ip()
    if not _check_rate_limit(ip):
        logger.warning("Rate limit exceeded for IP: %s", ip)
        return jsonify({
            "error": f"Free tier limit reached. You may run up to {MONTHLY_ANALYSIS_LIMIT} analyses per month. Resets on the 1st of next month."
        }), 429

    try:
        if 'file' in request.files:
            upload = request.files['file']
            try:
                _safe_filename(upload.filename or "")
            except ValueError:
                return jsonify({"error": "The filename is invalid. Please rename your file and try again."}), 400
            raw_bytes = upload.read()
            try:
                csv_data = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                csv_data = raw_bytes.decode("latin-1")
            commission_per_trade = request.form.get("commission_per_trade", None)
        elif request.is_json:
            body = request.get_json(silent=True) or {}
            csv_data = body.get("csv_data", "")
            if not isinstance(csv_data, str):
                return jsonify({"error": "csv_data must be a string."}), 400
            commission_per_trade = body.get("commission_per_trade", None)
        else:
            return jsonify({"error": "No file received. Please upload a CSV file or send csv_data in the request body."}), 400

        # Reject empty uploads before any parsing
        if not csv_data or not csv_data.strip():
            return jsonify({"error": "The uploaded file is empty. Please upload a valid CSV file."}), 400

        # Validate commission_per_trade if provided
        if commission_per_trade is not None:
            try:
                commission_per_trade = float(commission_per_trade)
            except (TypeError, ValueError):
                return jsonify({"error": "commission_per_trade must be a number."}), 400
            if commission_per_trade < 0:
                return jsonify({"error": "commission_per_trade must be a non-negative number."}), 400
            result = analyze_uploaded_trades(csv_data, commission_per_trade=commission_per_trade)
        else:
            result = analyze_uploaded_trades(csv_data)

        if isinstance(result, dict) and result.get("error"):
            return jsonify(result), 400
        return jsonify(result), 200

    except FreeTierLimitExceeded as exc:
        logger.warning("CSV upload rejected (free tier limit): %s", exc)
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        # Other ValueErrors (e.g. bad format) still return 400
        logger.warning("CSV upload rejected (ValueError): %s", exc)
        return jsonify({"error": str(exc)}), 400
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("analyze_backtest error: %s", exc)
        return jsonify({"error": "An unexpected error occurred while processing your file. Please try again."}), 500


if __name__ == "__main__":
    # Get port from environment variable (Render provides this) or default to 5001
    try:
        port = int(os.environ.get('PORT', 5001))
    except ValueError as e:
        raise ValueError("PORT must be a valid integer") from e
    
    # Run the app on all interfaces for Render deployment
    app.run(host='0.0.0.0', port=port, debug=False)