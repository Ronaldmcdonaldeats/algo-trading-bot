# 📁 Folder Structure Overview

## 📂 Root Level (Clean!)

```
algo-trading-bot/
├── 📄 README.md                  # Project overview (START HERE)
├── 📄 DOCUMENTATION.md           # Complete reference (ALL INFO)
├── 📄 AGENTS.md                  # Agent guidance
├── 📄 pyproject.toml             # Package configuration
├── 📄 docker-compose.yml         # Docker setup
├── 📄 Dockerfile                 # Container definition
│
├── 📁 src/                       # Main source code
│   └── trading_bot/              # Bot package (core implementation)
│
├── 📁 tests/                     # Unit tests
├── 📁 configs/                   # Configuration files (default.yaml)
├── 📁 scripts/                   # Setup scripts (bootstrap.ps1)
├── 📁 notebooks/                 # Research notebooks
│
├── 📁 tools/                     # ⭐ Verification & demo scripts
│   ├── verify_improvements.py    # Verify all 3 improvements
│   ├── verify_learning.py        # Verify learning systems
│   ├── demo_learning_monitoring.ps1
│   └── test_learning_cli.ps1
│
├── 📁 data/                      # ⭐ Runtime data
│   └── trades.sqlite             # Trading database
│
├── 📁 logs/                      # ⭐ Runtime logs
│   └── bot_debug.log             # Debug log
│
├── 📁 .cache/                    # Cache (hidden)
├── 📁 .venv/                     # Virtual environment (hidden)
├── 📁 .git/                      # Git repo (hidden)
└── 📁 .pytest_cache/             # Pytest cache (hidden)
```

## 🎯 Where To Find Things

| Need | Location | Command |
|------|----------|---------|
| Start trading | `README.md` | `python -m trading_bot start --period 60d` |
| Learn everything | `DOCUMENTATION.md` | Open in editor |
| Source code | `src/trading_bot/` | Edit strategies, engine, etc. |
| Run tests | `tests/` | `pytest` |
| Verify bot works | `tools/verify_improvements.py` | `python tools/verify_improvements.py` |
| Monitor learning | `tools/test_learning_cli.ps1` | `.\tools\test_learning_cli.ps1` |
| Trading data | `data/trades.sqlite` | Query with `sqlite3 data/trades.sqlite` |
| Debug logs | `logs/bot_debug.log` | Check if errors |
| Configuration | `configs/default.yaml` | Edit trading parameters |

## ✅ Clean Organization

✅ **Source code** - Organized by feature (engine, strategies, learning, etc.)
✅ **Tools** - All verification/demo scripts in one place
✅ **Data** - Separate from code (easy to backup/delete)
✅ **Logs** - Separate from code (easy to clean)
✅ **Config** - YAML files separate from code
✅ **Hidden** - Cache/venv/git kept out of sight

## 🧹 Cleanup Commands

Keep it clean:

```powershell
# Clear cache (safe to delete anytime)
rm -r .cache, .pytest_cache, .ruff_cache

# Archive old logs
mv logs/bot_debug.log logs/bot_debug.log.bak

# Backup database before cleanup
cp data/trades.sqlite data/trades.sqlite.bak

# Clean old trading data (keep last 7 days)
python -m trading_bot maintenance cleanup --days-keep 7
```

---

**Last Updated:** January 23, 2026
