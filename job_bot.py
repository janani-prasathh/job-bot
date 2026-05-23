name: Daily Job Bot

on:
  schedule:
    - cron: '30 1 * * *'
  workflow_dispatch:

jobs:
  run-job-bot:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Test full pipeline (scraping + Gemini + email)
        env:
          YOUR_NAME:          ${{ secrets.YOUR_NAME }}
          YOUR_EMAIL:         ${{ secrets.YOUR_EMAIL }}
          YOUR_GMAIL:         ${{ secrets.YOUR_GMAIL }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          GEMINI_API_KEY:     ${{ secrets.GEMINI_API_KEY }}
          JOB_KEYWORDS:       ${{ secrets.JOB_KEYWORDS }}
          JOB_LOCATION:       ${{ secrets.JOB_LOCATION }}
        run: python test_full_pipeline.py

      - name: Run Job Bot
        env:
          YOUR_NAME:          ${{ secrets.YOUR_NAME }}
          YOUR_EMAIL:         ${{ secrets.YOUR_EMAIL }}
          YOUR_GMAIL:         ${{ secrets.YOUR_GMAIL }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          GEMINI_API_KEY:     ${{ secrets.GEMINI_API_KEY }}
          JOB_KEYWORDS:       ${{ secrets.JOB_KEYWORDS }}
          JOB_LOCATION:       ${{ secrets.JOB_LOCATION }}
        run: python job_bot.py
