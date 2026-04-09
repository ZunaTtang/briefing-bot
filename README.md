# Crypto Evening Briefing Bot 🚀

An automated Telegram bot that provides professional crypto market briefings.

## Features
- **Daily Market Briefings**: Automatically generates and sends market reports at scheduled times (09:00 and 12:30 KST).
- **Data Integration**: Fetches data from multiple sources including:
  - ETF Flows (BTC/ETH)
  - Open Interest (OI) & Funding Rates (BTC/ETH/SOL)
  - Coinbase Premium
  - Market Indices (Fear & Greed, Altcoin Season)
- **AI Analysis**: Uses Anthropic's Claude API to generate professional, data-driven market interpretations.
- **Robust Scraper**: Custom scraping logic with error handling and retry mechanisms.

## Tech Stack
- **Python**: Core logic and scraping.
- **Telegram Bot API**: Distribution.
- **Claude API**: Content generation.
- **GCP Cloud Scheduler**: Automated execution.
- **Docker**: For easy deployment.

## Setup
1. Clone the repository.
2. Create a `.env` file with the following variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
   - (Add other environment variables as needed)
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python main.py
   ```

## License
MIT License
