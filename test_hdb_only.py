name: HDB Bidding Bot

on:
  schedule:
    # 1:00 AM UTC translates to 9:00 AM Singapore Time (SGT)
    - cron: '0 1 * * *'
  workflow_dispatch:

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install Dependencies
        # Added pandas for CSV fetching and playwright for E-Bidding DOM scraping
        run: |
          pip install requests pandas playwright
          python -m playwright install chromium

      - name: Run HDB Bidding Bot
        env:
          # Pulls your secure secrets from GitHub settings
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          PROXY_HOST: ${{ secrets.PROXY_HOST }}
          PROXY_PORT: ${{ secrets.PROXY_PORT }}
          PROXY_USER: ${{ secrets.PROXY_USER }}
          PROXY_PASS: ${{ secrets.PROXY_PASS }}
        run: python test_hdb_only.py
