import sqlite3
import subprocess
import json

# Get container ID
result = subprocess.run(
    ["docker", "ps", "-q", "-f", "name=trading-bot-auto"],
    capture_output=True,
    text=True
)
container_id = result.stdout.strip()

if not container_id:
    print("[ERROR] Container not found")
    exit(1)

# Run sqlite command in container
result = subprocess.run(
    ["docker", "exec", container_id, "sqlite3", "/app/trading_bot.db", 
     "SELECT COUNT(*) as total FROM orders; SELECT COUNT(*) as fills FROM fills; SELECT symbol, qty, side, status FROM orders LIMIT 10;"],
    capture_output=True,
    text=True
)

print("[BOT STATUS]")
print(result.stdout)
if result.stderr:
    print("[STDERR]")
    print(result.stderr)
