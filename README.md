# ExaSignal: AI-Powered Prediction Market Dashboard

ExaSignal is a real-time analytics dashboard for Polymarket, powered by AI (Groq, Exa, Gamma) to provide deep insights and "Whale Tracking" for prediction markets.

## 🚀 Quick Start

You need to run **two** terminal processes to start the full application:

### 1. Start the Backend API (Python)
This powers the data fetching, AI analysis, and database.

```bash
# Make sure you are in the project root
pip install -r requirements.txt
python -m uvicorn src.api.server:app --reload --port 8000
```
> The API will be available at [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Start the Frontend Dashboard (Next.js)
This runs the UI.

```bash
cd dashboard
npm install
npm run dev
```
> The Dashboard will be available at [http://localhost:3000](http://localhost:3000)

## 🔑 Environment Variables
Ensure you have a `.env` file in the root with:
```env
# AI Keys
GROQ_API_KEY=...
EXA_API_KEY=...
NEWSAPI_KEY=...

# Polymarket (Optional for generic usage, required for Whale Tracking)
POLYMARKET_API_KEY=...
POLYMARKET_SECRET=...
POLYMARKET_PASSPHRASE=...
```

## 🛠️ Features
- **Global Search**: Search any market on Polymarket.
- **AI Investigation**: Click "Investigate" to get an AI analysis of the market odds vs reality.
- **Whale Tracker**: Monitor large trades in real-time.
- **Sentiment Analysis**: Analyze news sentiment against market odds.
