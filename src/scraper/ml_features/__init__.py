"""ML feature extraction sub-package.

Each phase module exposes a single ``run(target, payload)`` function that
enriches the shared ``FeaturePayload`` with its own metric keys.

Phase mapping
-------------
phase_1_fundamentals  → metrics 10-14  (yfinance + i3investor PBT/NP margins)
phase_2_valuation     → metrics 15-18  (yfinance + TradingView peer valuation)
phase_3_surprises     → metrics 1-5   (Investing.com / yfinance / i3investor)
phase_4_money_flow    → metrics 6-9   (i3investor Form 29B/29C + warrants)
phase_5_forward_looking → metric 21    (sector peer earnings sentiment)
"""
