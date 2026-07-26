#!/usr/bin/env bash
set -e

echo "=========================================="
echo "🚀 Starting SiteMind Services..."
echo "=========================================="

# 1. Backend
echo "-> Starting Backend (Port 8000)..."
cd backend
nohup bash ./run.sh > backend_out.log 2>&1 &
BACKEND_PID=$!
cd ..

# 2. Standards Service
echo "-> Starting Standards Service (Port 8010)..."
cd standards-service
nohup bash ./run.sh > standards_out.log 2>&1 &
STANDARDS_PID=$!
cd ..

# 3. Telegram Bot
echo "-> Starting Telegram Bot..."
cd telegram-bot
nohup bash ./run.sh > bot_out.log 2>&1 &
BOT_PID=$!
cd ..

# 4. Frontend
echo "-> Starting Frontend (Port 3000)..."
cd frontend
nohup npm run dev > frontend_out.log 2>&1 &
FRONTEND_PID=$!
cd ..

disown -a

echo ""
echo "✅ All services successfully launched in the background!"
echo ""
echo "🌐 Web Dashboard: http://localhost:3000"
echo "⚙️  Backend API:   http://localhost:8000"
echo "📘 Codebook API:  http://localhost:8010"
echo "🤖 Telegram Bot:  Active"
echo ""
echo "To shut down all services later, run:"
echo "kill $BACKEND_PID $STANDARDS_PID $BOT_PID $FRONTEND_PID"
echo "=========================================="
