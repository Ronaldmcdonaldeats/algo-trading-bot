from pathlib import Path

from trading_bot.configs import load_config


def test_load_default_config():
    cfg = load_config(Path("configs/default.yaml"))
    assert cfg.risk.max_risk_per_trade == 0.10
    assert cfg.risk.stop_loss_pct == 0.02
    assert cfg.risk.take_profit_pct == 0.05
