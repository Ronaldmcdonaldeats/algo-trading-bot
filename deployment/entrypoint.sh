#!/bin/bash
# Production WSGI server startup script

cd /app

# Run with Gunicorn for production
gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 4 \
  --worker-class sync \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  'trading_bot.ui.web:app'
