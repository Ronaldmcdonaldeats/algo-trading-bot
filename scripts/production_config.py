"""
Production Configuration System
Secure management of API keys, position limits, kill switches, and emergency controls
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import yaml

class ProductionConfig:
    """Production-ready configuration management"""
    
    def __init__(self):
        self.config_dir = Path('config')
        self.config_dir.mkdir(exist_ok=True)
        
        # Load or create configs
        self.broker_config = self._load_or_create('broker_config.yaml')
        self.position_limits = self._load_or_create('position_limits.yaml')
        self.emergency_controls = self._load_or_create('emergency_controls.yaml')
        self.monitoring_rules = self._load_or_create('monitoring_rules.yaml')
        self.api_credentials = self._load_or_create('api_credentials.yaml')
    
    def _load_or_create(self, filename: str) -> Dict[str, Any]:
        """Load config file or create default"""
        config_path = self.config_dir / filename
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        else:
            # Create default based on filename
            default = self._get_default_config(filename)
            self._save_config(config_path, default)
            return default
    
    def _save_config(self, path: Path, config: Dict):
        """Save config to file"""
        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    
    def _get_default_config(self, filename: str) -> Dict[str, Any]:
        """Get default configuration templates"""
        
        if filename == 'broker_config.yaml':
            return {
                'broker': 'interactive_brokers',  # or 'alpaca', 'td_ameritrade'
                'mode': 'paper',  # paper or live
                'account_type': 'margin',  # cash or margin
                'base_currency': 'USD',
                'commission_rate_pct': 0.001,  # 0.1%
                'market_data_source': 'live',  # live or cached
                'trading_hours': {
                    'market_open': '09:30',
                    'market_close': '16:00',
                    'premarket_start': '04:00',
                    'afterhours_end': '20:00',
                    'timezone': 'US/Eastern'
                },
                'execution': {
                    'order_type': 'market',  # market or limit
                    'time_in_force': 'day',  # day or gtc
                    'slippage_bps': 7
                }
            }
        
        elif filename == 'position_limits.yaml':
            return {
                'position_sizing': {
                    'per_trade_pct': 0.05,  # 5% per trade
                    'max_concentration_pct': 0.1774,  # 17.74% max per symbol
                    'max_positions': 20,
                    'max_sector_concentration': 0.30  # 30% max per sector
                },
                'portfolio_limits': {
                    'max_leverage': 1.0,  # 1.0 = no margin, 2.0 = 2x leverage
                    'min_cash_pct': 0.05,  # Keep 5% cash minimum
                    'max_equity_at_risk': 0.10  # 10% total portfolio risk
                },
                'daily_limits': {
                    'max_trades_per_day': 50,
                    'max_daily_loss_pct': 0.05,  # Stop trading if -5% in a day
                    'max_drawdown_pct': 0.10  # Stop trading if -10% max drawdown
                },
                'symbol_restrictions': {
                    'min_price': 1.0,  # Don't trade penny stocks
                    'min_daily_volume_usd': 500000,
                    'blacklist': ['SPY', 'QQQ'],  # Symbols to never trade
                    'whitelist': []  # If set, only trade these
                }
            }
        
        elif filename == 'emergency_controls.yaml':
            return {
                'kill_switches': {
                    'enabled': True,
                    'max_consecutive_losses': 5,  # Stop after 5 losses in a row
                    'max_daily_loss_usd': 5000,  # Stop if lose $5k in a day
                    'max_drawdown_percent': 15,  # Emergency stop at -15% drawdown
                    'circuit_breaker_wait_hours': 24  # Wait 24h before resuming
                },
                'alerts': {
                    'email_enabled': False,
                    'email_on_large_loss': True,  # Alert on loss > 3%
                    'email_on_large_gain': True,  # Alert on gain > 10%
                    'sms_enabled': False,
                    'slack_enabled': False
                },
                'emergency_actions': {
                    'auto_close_all_on_breach': False,  # Auto liquidate on limits
                    'reduce_position_size_on_stress': True,  # Halve sizes if stressed
                    'manual_confirmation_required': True  # Require manual OK to resume
                },
                'monitoring': {
                    'health_check_interval_seconds': 60,
                    'price_feed_timeout_seconds': 5,
                    'heartbeat_timeout_seconds': 30
                }
            }
        
        elif filename == 'monitoring_rules.yaml':
            return {
                'dashboards': {
                    'refresh_interval_seconds': 5,
                    'charts': {
                        'equity_curve': True,
                        'daily_returns': True,
                        'drawdown_chart': True,
                        'win_rate_chart': True,
                        'position_map': True
                    }
                },
                'alerts': {
                    'large_position_alert_pct': 0.15,  # Alert if position > 15%
                    'correlation_alert': 0.8,  # Alert if correlation > 0.8
                    'volatility_alert_pct': 0.30,  # Alert if portfolio volatility > 30%
                    'slippage_alert_bps': 20  # Alert if slippage > 20 bps
                },
                'performance_tracking': {
                    'target_return_pct': 7.0,  # Expected from backtest
                    'allowed_variance_pct': 5.0,  # ±5% variance allowed
                    'monthly_review': True,
                    'reoptimization_interval_days': 30
                }
            }
        
        elif filename == 'api_credentials.yaml':
            return {
                'interactive_brokers': {
                    'enabled': False,
                    'account_id': '${IB_ACCOUNT_ID}',  # From environment
                    'api_key': '${IB_API_KEY}',
                    'secret_key': '${IB_SECRET_KEY}',
                    'host': 'localhost',
                    'port': 7497
                },
                'alpaca': {
                    'enabled': False,
                    'api_key': '${ALPACA_API_KEY}',
                    'secret_key': '${ALPACA_SECRET_KEY}',
                    'base_url': 'https://paper-api.alpaca.markets'  # paper or live
                },
                'alpha_vantage': {
                    'enabled': False,
                    'api_key': '${AV_API_KEY}'
                },
                'encrypted': False,  # Set to True for production
                'credential_store': 'environment'  # environment or vault
            }
        
        return {}
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration for production"""
        errors = []
        warnings = []
        
        # Check broker config
        if self.broker_config.get('mode') == 'live':
            if not all(self.api_credentials.get(self.broker_config.get('broker'), {}).get(k) 
                      for k in ['api_key', 'secret_key']):
                errors.append("Live mode requires complete API credentials")
        
        # Check position limits
        limits = self.position_limits.get('position_sizing', {})
        if limits.get('per_trade_pct', 0) > limits.get('max_concentration_pct', 1):
            errors.append("Per-trade % cannot exceed max concentration %")
        
        # Check emergency controls
        if self.emergency_controls.get('kill_switches', {}).get('enabled'):
            if not any([self.emergency_controls.get('kill_switches', {}).get(k) 
                       for k in ['max_consecutive_losses', 'max_daily_loss_usd', 'max_drawdown_percent']]):
                warnings.append("Kill switches enabled but no limits configured")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_broker_settings(self) -> Dict[str, Any]:
        """Get broker configuration"""
        return self.broker_config
    
    def get_position_limits(self) -> Dict[str, Any]:
        """Get position sizing rules"""
        return self.position_limits
    
    def get_emergency_controls(self) -> Dict[str, Any]:
        """Get emergency kill switches and controls"""
        return self.emergency_controls
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring and alerting configuration"""
        return self.monitoring_rules
    
    def update_limits(self, updates: Dict[str, Any]):
        """Update position limits dynamically"""
        self.position_limits.update(updates)
        self._save_config(self.config_dir / 'position_limits.yaml', self.position_limits)
    
    def export_for_deployment(self, export_path: str = 'config/production_deploy.json'):
        """Export sanitized config for deployment"""
        export = {
            'broker': self.broker_config,
            'position_limits': self.position_limits,
            'emergency_controls': self.emergency_controls,
            'monitoring': self.monitoring_rules,
            'validation': self.validate(),
            'exported_at': datetime.now().isoformat()
        }
        
        # Don't export credentials
        export['broker'].pop('api_credentials', None)
        
        with open(export_path, 'w') as f:
            json.dump(export, f, indent=2)
        
        return export_path

def main():
    """Test configuration system"""
    print("\n" + "="*80)
    print("PRODUCTION CONFIGURATION SYSTEM")
    print("="*80)
    
    config = ProductionConfig()
    
    print("\n✓ Configuration loaded successfully")
    print(f"✓ Config directory: {config.config_dir}")
    
    # Validate
    validation = config.validate()
    print(f"\n{'='*80}")
    print("VALIDATION RESULTS")
    print('='*80)
    
    if validation['valid']:
        print("✓ Configuration is VALID for production")
    else:
        print("✗ Configuration has ERRORS:")
        for error in validation['errors']:
            print(f"  - {error}")
    
    if validation['warnings']:
        print("\n⚠ Warnings:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
    
    # Show settings
    print(f"\n{'='*80}")
    print("BROKER SETTINGS")
    print('='*80)
    broker = config.get_broker_settings()
    print(f"Broker: {broker.get('broker')}")
    print(f"Mode: {broker.get('mode')} ({'LIVE - BE CAREFUL' if broker.get('mode') == 'live' else 'Paper'})")
    print(f"Commission: {broker.get('commission_rate_pct') * 100}%")
    print(f"Trading Hours: {broker['trading_hours']['market_open']} - {broker['trading_hours']['market_close']}")
    
    print(f"\n{'='*80}")
    print("POSITION LIMITS")
    print('='*80)
    limits = config.get_position_limits()
    sizing = limits.get('position_sizing', {})
    daily = limits.get('daily_limits', {})
    
    print(f"Per-Trade Size: {sizing.get('per_trade_pct') * 100}%")
    print(f"Max Concentration: {sizing.get('max_concentration_pct') * 100}%")
    print(f"Max Positions: {sizing.get('max_positions')}")
    print(f"Max Daily Loss: {daily.get('max_daily_loss_pct') * 100}%")
    print(f"Max Drawdown: {daily.get('max_drawdown_pct') * 100}%")
    
    print(f"\n{'='*80}")
    print("EMERGENCY CONTROLS")
    print('='*80)
    emergency = config.get_emergency_controls()
    kills = emergency.get('kill_switches', {})
    
    print(f"Kill Switches Enabled: {kills.get('enabled')}")
    if kills.get('enabled'):
        print(f"  - Max Consecutive Losses: {kills.get('max_consecutive_losses')}")
        print(f"  - Max Daily Loss: ${kills.get('max_daily_loss_usd'):,}")
        print(f"  - Max Drawdown: {kills.get('max_drawdown_percent') * 100}%")
        print(f"  - Circuit Breaker Wait: {kills.get('circuit_breaker_wait_hours')} hours")
    
    print(f"\n{'='*80}")
    print("EXPORT FOR DEPLOYMENT")
    print('='*80)
    
    export_path = config.export_for_deployment()
    print(f"✓ Configuration exported to: {export_path}")
    
    print("\n" + "="*80)
    print("Ready for production deployment!")
    print("="*80)

if __name__ == '__main__':
    main()
