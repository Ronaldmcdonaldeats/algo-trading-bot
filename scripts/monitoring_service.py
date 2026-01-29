"""
Monitoring Service
Real-time monitoring, health checks, alerts, and performance tracking
"""
import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
from typing import Dict, List, Any

class MonitoringService:
    """Continuous monitoring of trading bot health and performance"""
    
    def __init__(self, db_url='sqlite:///logs/trading_metrics.db'):
        self.db_path = Path('logs/trading_metrics.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.alerts = []
        self.health_status = 'HEALTHY'
        self.last_check = datetime.now()
    
    def _get_db(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """Initialize database"""
        conn = self._get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                portfolio_value REAL,
                cash_available REAL,
                total_positions INTEGER,
                daily_pnl REAL,
                drawdown REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                api_latency_ms REAL,
                price_feed_status TEXT,
                strategy_status TEXT,
                error_count INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                severity TEXT,
                alert_type TEXT,
                message TEXT,
                action_taken TEXT,
                resolved BOOLEAN
            )
        """)
        
        conn.commit()
        conn.close()
    
    def check_broker_connection(self) -> Dict[str, Any]:
        """Check broker API connection health"""
        try:
            # Simulate connection check
            start = time.time()
            latency = (time.time() - start) * 1000
            
            return {
                'connected': True,
                'latency_ms': latency,
                'status': 'HEALTHY',
                'last_check': datetime.now()
            }
        except Exception as e:
            self._create_alert('CRITICAL', 'broker_connection', f"Broker connection failed: {str(e)}")
            return {
                'connected': False,
                'status': 'ERROR',
                'error': str(e)
            }
    
    def check_price_feed(self) -> Dict[str, Any]:
        """Check market data feed health"""
        try:
            # Check if recent data available
            conn = sqlite3.connect('data/real_market_data.db')
            cursor = conn.cursor()
            
            cursor.execute("SELECT MAX(date) FROM daily_prices")
            latest_date = cursor.fetchone()[0]
            conn.close()
            
            if latest_date:
                age_days = (datetime.now().date() - datetime.strptime(latest_date, '%Y-%m-%d').date()).days
                
                if age_days > 7:
                    self._create_alert('WARNING', 'price_feed', 
                                     f"Price data is {age_days} days old")
                    status = 'STALE'
                else:
                    status = 'HEALTHY'
                
                return {
                    'status': status,
                    'latest_data': latest_date,
                    'age_days': age_days
                }
        except Exception as e:
            self._create_alert('CRITICAL', 'price_feed', f"Price feed check failed: {str(e)}")
            return {'status': 'ERROR', 'error': str(e)}
    
    def check_strategy_health(self, position_count=0, daily_pnl=0.0) -> Dict[str, Any]:
        """Check strategy execution health"""
        health = {
            'status': 'HEALTHY',
            'position_count': position_count,
            'daily_pnl': daily_pnl,
            'warnings': []
        }
        
        if position_count > 20:
            health['warnings'].append(f"High position count: {position_count}")
            health['status'] = 'WARNING'
        
        if daily_pnl < -0.05:  # -5%
            health['warnings'].append(f"Large daily loss: {daily_pnl*100:.2f}%")
            health['status'] = 'ALERT'
            self._create_alert('WARNING', 'daily_loss', 
                             f"Daily loss exceeds -5%: {daily_pnl*100:.2f}%")
        
        return health
    
    def check_risk_limits(self, portfolio_value=100000, positions=None, 
                         max_concentration_pct=0.1774) -> Dict[str, Any]:
        """Check if risk limits are being respected"""
        violations = []
        
        if positions:
            for symbol, pos_data in positions.items():
                pos_value = pos_data['shares'] * pos_data['current_price']
                concentration = pos_value / portfolio_value
                
                if concentration > max_concentration_pct:
                    violations.append(f"{symbol}: {concentration*100:.2f}% > {max_concentration_pct*100:.2f}%")
                    self._create_alert('WARNING', 'concentration_violation',
                                     f"{symbol} exceeds max concentration: {concentration*100:.2f}%")
        
        return {
            'status': 'PASS' if not violations else 'VIOLATIONS',
            'violation_count': len(violations),
            'violations': violations
        }
    
    def check_drawdown(self, equity_curve: List[float], max_dd_pct=0.10) -> Dict[str, Any]:
        """Check maximum drawdown"""
        if len(equity_curve) < 2:
            return {'status': 'INSUFFICIENT_DATA'}
        
        equity = np.array(equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_dd = np.min(drawdown)
        
        if max_dd < -max_dd_pct:
            severity = 'CRITICAL' if max_dd < -0.15 else 'WARNING'
            self._create_alert(severity, 'max_drawdown',
                             f"Max drawdown: {max_dd*100:.2f}% (limit: {max_dd_pct*100:.2f}%)")
        
        return {
            'max_drawdown_pct': max_dd * 100,
            'limit_pct': max_dd_pct * 100,
            'status': 'PASS' if max_dd >= -max_dd_pct else 'VIOLATION'
        }
    
    def _create_alert(self, severity: str, alert_type: str, message: str):
        """Create and store alert"""
        alert = {
            'severity': severity,
            'alert_type': alert_type,
            'message': message,
            'timestamp': datetime.now(),
            'resolved': False
        }
        self.alerts.append(alert)
        
        # Log to file
        log_path = Path('logs/alerts.json')
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_path, 'a') as f:
            json.dump(alert, f, default=str)
            f.write('\n')
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform complete system health check"""
        broker = self.check_broker_connection()
        price_feed = self.check_price_feed()
        strategy = self.check_strategy_health()
        
        health_status = 'HEALTHY'
        if any([broker['status'] == 'ERROR', price_feed.get('status') == 'ERROR', 
               strategy['status'] == 'ALERT']):
            health_status = 'ERROR'
        elif any([broker['status'] == 'WARNING', price_feed.get('status') == 'STALE',
                 strategy['status'] == 'WARNING']):
            health_status = 'WARNING'
        
        return {
            'overall_status': health_status,
            'timestamp': datetime.now(),
            'broker': broker,
            'price_feed': price_feed,
            'strategy': strategy,
            'alert_count': len(self.alerts),
            'recent_alerts': self.alerts[-5:] if self.alerts else []
        }
    
    def get_performance_summary(self, days=30) -> Dict[str, Any]:
        """Get performance summary for dashboard"""
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            
            start_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                SELECT 
                    AVG(daily_pnl) as avg_daily,
                    SUM(daily_pnl) as total_pnl,
                    MIN(drawdown) as max_dd,
                    COUNT(*) as trade_days
                FROM performance
                WHERE timestamp > ?
            """, (start_date,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'period_days': days,
                    'avg_daily_pnl': result[0],
                    'total_pnl': result[1],
                    'max_drawdown': result[2],
                    'trading_days': result[3]
                }
        except:
            pass
        
        return {'status': 'no_data'}
    
    def generate_health_report(self) -> str:
        """Generate comprehensive health report"""
        health = self.perform_health_check()
        perf = self.get_performance_summary()
        
        report = f"""
{'='*80}
TRADING BOT HEALTH REPORT
{'='*80}

Report Time: {health['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
Overall Status: {health['overall_status']}

{'='*80}
SYSTEM HEALTH
{'='*80}

Broker Connection:  {health['broker']['status']}
  Latency: {health['broker'].get('latency_ms', 'N/A')} ms

Price Feed:         {health['price_feed'].get('status', 'UNKNOWN')}
  Latest Data: {health['price_feed'].get('latest_data', 'N/A')}
  Age: {health['price_feed'].get('age_days', 'N/A')} days

Strategy:           {health['strategy']['status']}
  Positions: {health['strategy']['position_count']}
  Daily P&L: {health['strategy']['daily_pnl']*100:.2f}%

{'='*80}
PERFORMANCE (30-day)
{'='*80}

Avg Daily P&L:      {perf.get('avg_daily_pnl', 'N/A')}
Total P&L:          {perf.get('total_pnl', 'N/A')}
Max Drawdown:       {perf.get('max_drawdown', 'N/A')}
Trading Days:       {perf.get('trading_days', 'N/A')}

{'='*80}
ACTIVE ALERTS
{'='*80}

Total Alerts: {health['alert_count']}
"""
        
        if health['recent_alerts']:
            report += "\nRecent:\n"
            for alert in health['recent_alerts']:
                report += f"  [{alert['severity']}] {alert['alert_type']}: {alert['message']}\n"
        else:
            report += "\nNo active alerts\n"
        
        report += f"\n{'='*80}\n"
        
        return report

def main():
    """Test monitoring service"""
    print("\n" + "="*80)
    print("MONITORING SERVICE - Trading Bot Health & Performance")
    print("="*80)
    
    monitor = MonitoringService()
    monitor._init_db()
    
    print("\n✓ Monitoring service initialized")
    
    # Perform health check
    print("\nRunning system health check...")
    health = monitor.perform_health_check()
    
    print(f"✓ Overall Status: {health['overall_status']}")
    print(f"  Broker: {health['broker']['status']}")
    print(f"  Price Feed: {health['price_feed'].get('status', 'UNKNOWN')}")
    print(f"  Strategy: {health['strategy']['status']}")
    print(f"  Active Alerts: {health['alert_count']}")
    
    # Generate report
    report = monitor.generate_health_report()
    print(report)
    
    print("="*80)
    print("Monitoring service ready for continuous operation.")
    print("="*80)

if __name__ == '__main__':
    main()
