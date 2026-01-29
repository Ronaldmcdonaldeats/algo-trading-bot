-- Trading Bot Database Schema
-- PostgreSQL initialization script

-- Create tables for trade tracking
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(10) NOT NULL,
    entry_date DATE,
    entry_price DECIMAL(10, 4),
    exit_date DATE,
    exit_price DECIMAL(10, 4),
    shares INT,
    profit DECIMAL(15, 2),
    loss DECIMAL(15, 2),
    return_pct DECIMAL(8, 4),
    win_loss VARCHAR(10),
    status VARCHAR(20) DEFAULT 'CLOSED',
    notes TEXT
);

-- Create table for backtest results
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    strategy_name VARCHAR(100),
    total_return DECIMAL(8, 4),
    num_trades INT,
    win_rate DECIMAL(8, 4),
    sharpe_ratio DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    profit_factor DECIMAL(8, 4),
    final_equity DECIMAL(15, 2),
    config_file VARCHAR(255),
    notes TEXT
);

-- Create table for live trading journal
CREATE TABLE IF NOT EXISTS trading_journal (
    id SERIAL PRIMARY KEY,
    entry_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50),
    symbol VARCHAR(10),
    action VARCHAR(20),
    quantity INT,
    price DECIMAL(10, 4),
    portfolio_value DECIMAL(15, 2),
    cash_available DECIMAL(15, 2),
    notes TEXT
);

-- Create table for daily performance
CREATE TABLE IF NOT EXISTS daily_performance (
    id SERIAL PRIMARY KEY,
    trade_date DATE UNIQUE,
    starting_equity DECIMAL(15, 2),
    ending_equity DECIMAL(15, 2),
    daily_return DECIMAL(8, 4),
    num_trades INT,
    winning_trades INT,
    losing_trades INT,
    max_drawdown DECIMAL(8, 4),
    notes TEXT
);

-- Create table for risk metrics
CREATE TABLE IF NOT EXISTS risk_metrics (
    id SERIAL PRIMARY KEY,
    record_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    portfolio_value DECIMAL(15, 2),
    total_positions INT,
    max_position_concentration DECIMAL(8, 4),
    portfolio_risk_pct DECIMAL(8, 4),
    cash_pct DECIMAL(8, 4),
    num_violations INT,
    alert_level VARCHAR(20),
    notes TEXT
);

-- Create table for strategy parameters (history)
CREATE TABLE IF NOT EXISTS strategy_parameters (
    id SERIAL PRIMARY KEY,
    deployed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    strategy_version VARCHAR(50),
    entry_threshold DECIMAL(8, 4),
    profit_target DECIMAL(8, 4),
    stop_loss DECIMAL(8, 4),
    position_size_pct DECIMAL(8, 4),
    max_position_pct DECIMAL(8, 4),
    momentum_weight DECIMAL(8, 4),
    rsi_weight DECIMAL(8, 4),
    backtest_return DECIMAL(8, 4),
    status VARCHAR(20),
    notes TEXT
);

-- Create table for alerts and events
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(20),
    alert_type VARCHAR(100),
    message TEXT,
    action_taken VARCHAR(255),
    resolved BOOLEAN DEFAULT FALSE
);

-- Create indexes for performance
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_date ON trades(entry_date);
CREATE INDEX idx_backtest_date ON backtest_results(run_date);
CREATE INDEX idx_journal_date ON trading_journal(entry_date);
CREATE INDEX idx_performance_date ON daily_performance(trade_date);
CREATE INDEX idx_alerts_severity ON alerts(severity);
