"""Alert Configuration System."""

import json
from pathlib import Path
from typing import Dict

class AlertConfig:
    """Manages alert threshold configuration."""
    
    def __init__(self, config_file: str = "data/alert_config.json"):
        self.config_file = Path(config_file)
        self.defaults = {
            'trade_alerts': True,
            'risk_alerts': True,
            'signal_alerts': True,
            'market_alerts': True,
            'thresholds': {
                'drawdown_pct': 5.0,  # Alert if drawdown > 5%
                'position_size_pct': 15.0,  # Alert if single position > 15%
                'leverage_max': 1.5,  # Alert if leverage > 1.5x
                'volatility_threshold': 3.0,  # Alert if volatility > 3 std devs
                'price_move_pct': 10.0,  # Alert if price moves > 10% in 1 hour
            },
            'notification_channels': {
                'dashboard': True,
                'email': False,
                'sms': False,
            }
        }
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or use defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return self.defaults.copy()
    
    def save_config(self, new_config: Dict) -> bool:
        """Save configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(new_config, f, indent=2)
            self.config = new_config
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False
    
    def get_config(self) -> Dict:
        """Get current configuration."""
        return self.config
    
    def update_threshold(self, key: str, value: float) -> bool:
        """Update a specific threshold value."""
        if key in self.config['thresholds']:
            self.config['thresholds'][key] = value
            return self.save_config(self.config)
        return False
    
    def toggle_alert_type(self, alert_type: str, enabled: bool) -> bool:
        """Enable/disable specific alert type."""
        if f'{alert_type}_alerts' in self.config:
            self.config[f'{alert_type}_alerts'] = enabled
            return self.save_config(self.config)
        return False
    
    def should_alert(self, alert_type: str) -> bool:
        """Check if alert type is enabled."""
        return self.config.get(f'{alert_type}_alerts', True)
    
    def get_threshold(self, key: str) -> float:
        """Get specific threshold value."""
        return self.config['thresholds'].get(key, self.defaults['thresholds'].get(key, 0))


# Global instance
alert_config = AlertConfig()
