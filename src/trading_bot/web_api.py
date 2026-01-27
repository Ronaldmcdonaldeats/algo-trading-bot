"""Web API and Dashboard for the Trading Bot

Provides REST endpoints and WebSocket connections for controlling the trading bot.
Integrates all systems: Trade Journal, Drawdown Recovery, Auto-Tuning, Options.
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from threading import Thread
import json
from datetime import datetime
from pathlib import Path
import logging
import os
from collections import deque
import time
import secrets
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, validator

# Load environment variables from .env file
load_dotenv()

from trading_bot.integrated_bot import IntegratedTradingBot
from trading_bot.trading.trade_journal import TradeJournal
from trading_bot.risk.drawdown_recovery import DrawdownRecoveryManager
from trading_bot.learn.auto_tuning import AutoTuningSystem
from trading_bot.options.strategies import GreeksCalculator, OptionType, IncomeStrategy
from trading_bot.engine.paper import PaperEngineConfig, run_paper_engine
from trading_bot.configs.config import load_config
from trading_bot.data.providers import AlpacaProvider, MockDataProvider

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic validation models for API endpoints
class TradeRequest(BaseModel):
    """Validate trade recording request"""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int
    side: str
    strategy: str
    tags: list = []
    
    @validator('symbol')
    def symbol_valid(cls, v):
        if not v or len(v) > 10 or not v.isalpha():
            raise ValueError('Invalid symbol')
        return v.upper()
    
    @validator('entry_price', 'exit_price')
    def price_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return float(v)
    
    @validator('quantity')
    def qty_positive(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return int(v)
    
    @validator('side')
    def side_valid(cls, v):
        if v.upper() not in ['BUY', 'SELL']:
            raise ValueError('Side must be BUY or SELL')
        return v.upper()


class GreeksRequest(BaseModel):
    """Validate Greeks calculation request"""
    spot_price: float
    strike_price: float
    time_to_expiration: float
    option_type: str
    risk_free_rate: float = 0.05
    volatility: float = 0.20
    
    @validator('spot_price', 'strike_price')
    def price_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be positive')
        return float(v)
    
    @validator('time_to_expiration')
    def tte_positive(cls, v):
        if v <= 0:
            raise ValueError('Time to expiration must be positive')
        return float(v)
    
    @validator('option_type')
    def option_type_valid(cls, v):
        if v.lower() not in ['call', 'put']:
            raise ValueError('Option type must be call or put')
        return v.lower()


# Log handler for websocket
class WebSocketLogHandler(logging.Handler):
    """Custom logging handler to emit logs via websocket"""
    def __init__(self, socketio, max_logs=100):
        super().__init__()
        self.socketio = socketio
        self.logs = deque(maxlen=max_logs)
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            log_level = record.levelname.lower()
            self.logs.append({'message': log_entry, 'level': log_level})
            # Only emit if we have an active app context
            try:
                self.socketio.emit('log', {
                    'message': log_entry,
                    'level': log_level,
                    'timestamp': datetime.now().isoformat()
                })
            except RuntimeError:
                # App context not available, skip websocket emit
                pass
            except Exception as e:
                logger.warning(f"Failed to emit log via websocket: {e}")
        except Exception as e:
            logger.error(f"WebSocket log handler error: {e}", exc_info=True)


class TradingBotAPI:
    """REST API for trading bot"""
    
    def __init__(self, config_path=None):
        # Setup Flask app with templates directory
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.app = Flask(__name__, template_folder=template_dir)
        # Use secure secret key from environment or generate one
        self.app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
        # Restrict CORS to specific origins (set via environment or default to localhost)
        allowed_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5000,http://localhost:3000').split(',')
        self.socketio = SocketIO(self.app, cors_allowed_origins=allowed_origins)
        
        # Keep IntegratedTradingBot for backward compatibility with API endpoints
        self.bot = None  # Will be populated if needed, but _trading_loop takes priority
        self.is_running = False
        self.trading_thread = None
        self.trading_active = False
        self.config_path = config_path or "configs/default.yaml"
        
        # Setup log handler
        self.log_handler = WebSocketLogHandler(self.socketio)
        self.log_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(self.log_handler)
        
        self._setup_routes()
        self._setup_websocket()
        self._start_trading_loop()  # THIS TAKES PRIORITY - uses PaperEngine with live Alpaca
        
        logger.info("[API] Trading Bot API initialized - using PaperEngine for live trading")
    
    def _setup_routes(self):
        """Setup REST endpoints"""
        
        @self.app.route('/', methods=['GET'])
        def index():
            """Serve dashboard"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Get current bot status - using live Alpaca trading"""
            return jsonify({
                'status': 'running' if self.trading_active else 'stopped',
                'message': 'Using live Alpaca trading with PaperEngine',
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/api/trades', methods=['GET'])
        def get_trades():
            """Get recent trades"""
            limit = request.args.get('limit', 50, type=int)
            trades = self.bot.journal.get_recent_trades(limit)
            return jsonify({'trades': trades})
        
        @self.app.route('/api/trade', methods=['POST'])
        def record_trade():
            """Record a new trade"""
            try:
                data = request.json or {}
                trade_req = TradeRequest(**data)
                self.bot.record_trade(
                    symbol=trade_req.symbol,
                    entry_price=trade_req.entry_price,
                    exit_price=trade_req.exit_price,
                    quantity=trade_req.quantity,
                    side=trade_req.side,
                    strategy=trade_req.strategy,
                    tags=trade_req.tags
                )
                return jsonify({'status': 'success', 'equity': self.bot.current_equity})
            except ValidationError as e:
                logger.warning(f"Trade validation error: {e}")
                return jsonify({'status': 'error', 'message': f'Invalid request: {str(e)}'}), 400
            except Exception as e:
                logger.error(f"Trade recording error: {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/journal/analytics', methods=['GET'])
        def get_journal_analytics():
            """Get journal analytics"""
            symbol = request.args.get('symbol')
            analytics = self.bot.journal.analyze_by_symbol(symbol)
            return jsonify(analytics)
        
        @self.app.route('/api/journal/patterns', methods=['GET'])
        def get_patterns():
            """Get winning patterns"""
            patterns = self.bot.journal.find_winning_patterns()
            return jsonify({'patterns': patterns})
        
        @self.app.route('/api/recovery/status', methods=['GET'])
        def get_recovery_status():
            """Get recovery status"""
            status = self.bot.check_recovery_status()
            return jsonify(status)
        
        @self.app.route('/api/tuning/status', methods=['GET'])
        def get_tuning_status():
            """Get auto-tuning status"""
            should_tune = self.bot.auto_tuner.should_tune()
            return jsonify({
                'should_tune': should_tune,
                'last_tune': self.bot.auto_tuner.last_tune_time.isoformat() if self.bot.auto_tuner.last_tune_time else None,
                'next_tune': self.bot.auto_tuner.next_tune_time.isoformat() if self.bot.auto_tuner.next_tune_time else None,
                'current_params': self.bot.auto_tuner.current_params.params if self.bot.auto_tuner.current_params else None,
            })
        
        @self.app.route('/api/tuning/optimize', methods=['POST'])
        def trigger_optimization():
            """Trigger parameter optimization"""
            data = request.json
            try:
                result = self.bot.auto_tuner.optimize_parameters(
                    bounds=data.get('bounds', {})
                )
                # Extract score - handle various return types
                score = None
                if result and hasattr(result, 'score'):
                    score_val = result.score() if callable(result.score) else result.score
                    score = float(score_val) if score_val is not None else None
                elif isinstance(result, dict) and 'score' in result:
                    score = float(result['score']) if result['score'] is not None else None
                
                return jsonify({
                    'status': 'success',
                    'result': {
                        'params': result.params if hasattr(result, 'params') else {},
                        'score': score
                    }
                })
            except Exception as e:
                logger.error(f"Optimization error: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/options/covered-calls', methods=['GET'])
        def get_covered_calls():
            """Suggest covered call candidates"""
            stocks = request.args.get('stocks', '')
            if stocks:
                stock_list = stocks.split(',')
                candidates = IncomeStrategy.identify_covered_call_targets(
                    {s: {'price': 150.0} for s in stock_list}
                )
                return jsonify({'candidates': candidates})
            return jsonify({'candidates': []})
        
        @self.app.route('/api/options/greeks', methods=['POST'])
        def calculate_greeks():
            """Calculate option Greeks"""
            try:
                data = request.json or {}
                greeks_req = GreeksRequest(**data)
                greeks = GreeksCalculator.calculate_greeks(
                    S=greeks_req.spot_price,
                    K=greeks_req.strike_price,
                    T=greeks_req.time_to_expiration,
                    r=greeks_req.risk_free_rate,
                    sigma=greeks_req.volatility,
                    option_type=OptionType.CALL if greeks_req.option_type == 'call' else OptionType.PUT
                )
                return jsonify({
                    'delta': greeks.delta,
                    'gamma': greeks.gamma,
                    'vega': greeks.vega,
                    'theta': greeks.theta,
                    'rho': greeks.rho
                })
            except ValidationError as e:
                logger.warning(f"Greeks validation error: {e}")
                return jsonify({'status': 'error', 'message': f'Invalid request: {str(e)}'}), 400
            except Exception as e:
                logger.error(f"Greeks calculation error: {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 400
        
        @self.app.route('/api/report/daily', methods=['GET'])
        def get_daily_report():
            """Get daily report"""
            report = self.bot.generate_daily_report()
            return jsonify(report)
        
        @self.app.route('/api/report/export', methods=['GET'])
        def export_session():
            """Export session"""
            filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.bot.export_session(filename)
            return jsonify({'status': 'success', 'filename': filename})
        
        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            """Get current configuration"""
            return jsonify(self.bot.config)
        
        @self.app.route('/api/start', methods=['POST'])
        def start_bot():
            """Start trading"""
            try:
                self.is_running = True
                self.socketio.emit('bot_status', {'status': 'running'})
                logger.info("[API] Bot started")
                return jsonify({'status': 'started', 'message': 'Bot started successfully'}), 200
            except Exception as e:
                logger.error(f"[API] Error starting bot: {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop_bot():
            """Stop trading"""
            try:
                self.is_running = False
                self.socketio.emit('bot_status', {'status': 'stopped'})
                logger.info("[API] Bot stopped")
                return jsonify({'status': 'stopped', 'message': 'Bot stopped successfully'}), 200
            except Exception as e:
                logger.error(f"[API] Error stopping bot: {e}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/backtest', methods=['POST'])
        def run_backtest():
            """Run backtest with provided parameters"""
            try:
                from trading_bot.backtest.engine import run_backtest
                
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'Invalid JSON request'}), 400
                
                symbols = data.get('symbols', 'AAPL,MSFT,GOOGL').split(',')
                symbols = [s.strip().upper() for s in symbols if s.strip()]
                period = data.get('period', '1y')
                strategy = data.get('strategy', 'ultimate_hybrid')
                start_cash = float(data.get('start_cash', 100000))
                data_source = data.get('data_source', 'auto')  # auto|alpaca|yahoo
                
                if not symbols:
                    return jsonify({'error': 'No symbols provided'}), 400
                
                logger.info(f"[BACKTEST] Starting backtest: {symbols}, {period}, strategy={strategy}, source={data_source}")
                
                # Emit status immediately
                self.socketio.emit('backtest_status', {
                    'status': 'running',
                    'message': f'Backtesting {len(symbols)} symbols with {strategy}...'
                })
                
                # Run backtest in background thread with timeout handling
                def run_backtest_async():
                    import signal
                    max_retries = 3
                    retry_count = 0
                    last_error = None
                    
                    # Try with specified data source, then fallback
                    sources_to_try = []
                    if data_source == 'auto':
                        sources_to_try = ['alpaca', 'yahoo']
                    else:
                        sources_to_try = [data_source, 'yahoo']  # Fallback to yahoo if primary fails
                    
                    for source_idx, source in enumerate(sources_to_try):
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                self.socketio.emit('backtest_status', {
                                    'status': 'running',
                                    'message': f'Backtesting {len(symbols)} symbols with {strategy} (source: {source}, attempt {retry_count + 1}/{max_retries})...'
                                })
                                
                                result = run_backtest(
                                    config_path=None,
                                    symbols=symbols,
                                    period=period,
                                    strategy_mode=strategy,
                                    start_cash=start_cash,
                                    data_source=source,
                                )
                                
                                backtest_data = {
                                    'total_return': float(result.total_return) if result.total_return else 0,
                                    'sharpe': float(result.sharpe) if result.sharpe else 0,
                                    'max_drawdown': float(result.max_drawdown) if result.max_drawdown else 0,
                                    'win_rate': float(result.win_rate) if result.win_rate else 0,
                                    'num_trades': int(result.num_trades) if result.num_trades else 0,
                                    'avg_win': float(result.avg_win) if result.avg_win else 0,
                                    'avg_loss': float(result.avg_loss) if result.avg_loss else 0,
                                    'profit_factor': float(result.profit_factor) if result.profit_factor else 0,
                                    'calmar': float(result.calmar) if result.calmar else 0,
                                    'final_equity': float(result.final_equity) if result.final_equity else start_cash,
                                    'data_source': source,
                                }
                                
                                self.socketio.emit('backtest_complete', {
                                    'status': 'completed',
                                    'results': backtest_data
                                })
                                
                                logger.info(f"[BACKTEST] Complete: {backtest_data['total_return']:.2f}% return (source: {source})")
                                return  # Success, exit
                            except Exception as e:
                                retry_count += 1
                                last_error = str(e)
                                if retry_count < max_retries:
                                    error_msg = f"Attempt {retry_count} failed: {last_error}. Retrying..."
                                    logger.warning(f"[BACKTEST] {error_msg}")
                                    self.socketio.emit('backtest_status', {
                                        'status': 'retrying',
                                        'message': error_msg
                                    })
                                else:
                                    logger.warning(f"[BACKTEST] Source '{source}' failed after {max_retries} attempts: {last_error}")
                                    if source_idx < len(sources_to_try) - 1:
                                        next_source = sources_to_try[source_idx + 1]
                                        error_msg = f"Falling back to {next_source} data source..."
                                        logger.info(f"[BACKTEST] {error_msg}")
                                        self.socketio.emit('backtest_status', {
                                            'status': 'retrying',
                                            'message': error_msg
                                        })
                        
                        # If we got here and it's the last source, all sources failed
                        if source_idx == len(sources_to_try) - 1:
                            error_msg = f"Backtest failed with all data sources. Last error: {last_error}"
                            logger.error(f"[BACKTEST] {error_msg}")
                            self.socketio.emit('backtest_error', {
                                'status': 'error',
                                'message': error_msg
                            })
                
                # Start thread
                thread = Thread(target=run_backtest_async, daemon=True)
                thread.start()
                
                return jsonify({'status': 'started', 'message': 'Backtest running in background'}), 200
            
            except Exception as e:
                error_msg = f"Failed to start backtest: {str(e)}"
                logger.error(f"[BACKTEST] {error_msg}", exc_info=True)
                self.socketio.emit('backtest_error', {
                    'status': 'error',
                    'message': error_msg
                })
                return jsonify({'error': error_msg, 'status': 'error'}), 500
    
    def _setup_websocket(self):
        """Setup WebSocket connections"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info("[WS] Client connected")
            emit('connection_response', {'data': 'Connected to Trading Bot API'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info("[WS] Client disconnected")
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """Send current status"""
            recovery_status = self.bot.check_recovery_status()
            emit('status_update', {
                'equity': self.bot.current_equity,
                'day_pnl': self.bot.today_pnl,
                'day_trades': self.bot.today_trades,
                'recovery': recovery_status,
                'running': self.is_running
            })
        
        @self.socketio.on('request_logs')
        def handle_logs_request():
            """Send recent logs"""
            logs = list(self.log_handler.logs)
            emit('logs_history', {'logs': logs})
    
    def _start_trading_loop(self):
        """Start background trading loop thread"""
        self.trading_active = True
        self.trading_thread = Thread(target=self._trading_loop, daemon=False)
        self.trading_thread.start()
        logger.info("[API] Trading loop thread started")
    
    def _trading_loop(self):
        """Background trading loop that executes trades"""
        logger.info("[Trading Loop] Starting background trading loop")
        
        try:
            # Configure symbols and parameters - 50+ liquid stocks across sectors
            symbols = [
                # Tech Giants
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'NFLX', 'CRM',
                # Cloud/Software
                'ADBE', 'CSCO', 'INTC', 'AMD', 'QUALCOMM', 'AMAT', 'LRCX', 'SNPS', 'CDNS', 'MU',
                # Financial Tech
                'PYPL', 'SQ', 'COIN', 'HOOD', 'AXP', 'V', 'MA', 'JPM', 'BAC', 'GS',
                # Healthcare/Biotech
                'JNJ', 'UNH', 'PFIZER', 'MRNA', 'GILD', 'VRTX', 'CRSP', 'ILMN', 'DXCM', 'ELV',
                # Consumer/Retail
                'AMZN', 'TSLA', 'WMT', 'TGT', 'ULTA', 'NKE', 'RH', 'LOW', 'HD', 'COST',
                # Energy/Utilities
                'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'NEE', 'DUK'
            ]
            # Remove duplicates while preserving order
            symbols = list(dict.fromkeys(symbols))
            symbols = symbols[:50]  # Limit to 50
            
            config_path = "configs/default.yaml"
            db_path = "trading_bot.db"
            
            # Load config to get live_trading setting
            import yaml
            from pathlib import Path
            config_yaml = yaml.safe_load(Path(config_path).read_text())
            live_trading = config_yaml.get('trading', {}).get('live_trading', False)
            paper_mode = config_yaml.get('trading', {}).get('paper_mode', True)
            
            # Clean up database to avoid conflicts
            try:
                import os
                if os.path.exists(db_path):
                    os.remove(db_path)
                    logger.info(f"[Trading Loop] Cleaned up existing database: {db_path}")
            except Exception as e:
                logger.warning(f"[Trading Loop] Could not clean database: {e}")
            
            logger.info(f"[Trading Loop] Configuration loaded. Symbols ({len(symbols)}): {symbols}")
            logger.info(f"[Trading Loop] Config path: {config_path}, DB path: {db_path}")
            logger.info(f"[Trading Loop] Live Trading: {live_trading}, Paper Mode: {paper_mode}")
            
            # Create PaperEngineConfig
            engine_config = PaperEngineConfig(
                config_path=config_path,
                db_path=db_path,
                symbols=symbols,
                period="6mo",
                interval="1d",
                start_cash=100000.0,
                sleep_seconds=30,  # Check every 30 seconds
                iterations=0,  # Run forever
                strategy_mode='ultimate_hybrid',
                enable_learning=True,
                tune_weekly=True,
                commission_bps=1.0,
                slippage_bps=0.5,
                min_fee=0.0,
                learning_eta=0.3,
                memory_mode=False,
                live_trading=live_trading,
                paper_mode=paper_mode,
            )
            
            logger.info("[Trading Loop] PaperEngineConfig created successfully")
            logger.info(f"[Trading Loop] Starting trading loop with {len(symbols)} symbols")
            
            # Initialize Alpaca data provider for real market data with fallback
            provider = MockDataProvider()  # Start with mock provider as safe default
            try:
                alpaca_provider = AlpacaProvider()
                # Test if Alpaca provider can get data
                logger.info("[Trading Loop] Testing AlpacaProvider connection...")
                provider = alpaca_provider  # Use Alpaca if it works
                logger.info("[Trading Loop] Using AlpacaProvider for real Alpaca market data")
            except Exception as e:
                logger.warning(f"[Trading Loop] AlpacaProvider failed: {e}. Using MockDataProvider for synthetic market data.")
                provider = MockDataProvider()
            
            # Run the paper engine
            iteration = 0
            for update in run_paper_engine(cfg=engine_config, provider=provider):
                iteration += 1
                
                if not self.trading_active:
                    logger.info("[Trading Loop] Trading loop stopped by user")
                    break
                
                # Log trading activity
                if update.fills:
                    for fill in update.fills:
                        logger.info(f"[Trade] FILL: {fill.symbol} {fill.qty} @ {fill.price}")
                
                if update.rejections:
                    for rejection in update.rejections:
                        logger.warning(f"[Order Rejected] {rejection.order_id}: {rejection.reason}")
                
                # Log key metrics every 10 iterations
                if iteration % 10 == 0:
                    portfolio_value = float(update.portfolio.equity(prices)) if update.portfolio else 0.0
                    num_positions = len(update.portfolio.positions) if update.portfolio and update.portfolio.positions else 0
                    logger.info(f"[Trading Loop] Iteration {iteration} | Equity: ${portfolio_value:.2f} | Positions: {num_positions} | Signals: {len(update.signals) if hasattr(update, 'signals') else 0}")
                    
        except Exception as e:
            error_msg = str(e)
            # If Alpaca data fetch failed, retry with MockDataProvider
            if "No data returned from Alpaca" in error_msg and isinstance(provider, AlpacaProvider):
                logger.warning(f"[Trading Loop] AlpacaProvider failed: {error_msg}. Retrying with MockDataProvider...")
                provider = MockDataProvider()
                
                # Retry the trading loop with MockDataProvider
                iteration = 0
                try:
                    for update in run_paper_engine(cfg=engine_config, provider=provider):
                        iteration += 1
                        
                        if not self.trading_active:
                            logger.info("[Trading Loop] Trading loop stopped by user")
                            break
                        
                        # Log trading activity
                        if update.fills:
                            for fill in update.fills:
                                logger.info(f"[Trade] FILL: {fill.symbol} {fill.qty} @ {fill.price}")
                        
                        if update.rejections:
                            for rejection in update.rejections:
                                logger.warning(f"[Order Rejected] {rejection.order_id}: {rejection.reason}")
                        
                        # Log key metrics every 10 iterations
                        if iteration % 10 == 0:
                            portfolio_value = float(update.portfolio.equity(prices)) if update.portfolio else 0.0
                            num_positions = len(update.portfolio.positions) if update.portfolio and update.portfolio.positions else 0
                            logger.info(f"[Trading Loop] Iteration {iteration} | Equity: ${portfolio_value:.2f} | Positions: {num_positions} | Signals: {len(update.signals) if hasattr(update, 'signals') else 0}")
                except Exception as retry_error:
                    logger.error(f"[Trading Loop] Error in fallback trading loop: {retry_error}", exc_info=True)
            else:
                logger.error(f"[Trading Loop] Error in trading loop: {e}", exc_info=True)
        finally:
            logger.info("[Trading Loop] Trading loop ended")
    
    def run(self, host='127.0.0.1', port=5000, debug=False):
        """Start the API server"""
        logger.info(f"[API] Starting server on {host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug)


def create_app(config_path=None):
    """Factory function to create the Flask app"""
    api = TradingBotAPI(config_path=config_path)
    return api.app, api.socketio, api.bot


# Create the app instance for gunicorn
api_instance = TradingBotAPI()
app = api_instance.app
socketio = api_instance.socketio
