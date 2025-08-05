# European Super League (Stock Exchange) — ESL Trade

> A full-featured football simulator, in‑game sportsbook, stock‑exchange style trading of club "shares", derivatives (options) and digital over/under betting markets, all wrapped in a single Flask application.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Installation](#installation)
4. [Project Structure](#project-structure)
5. [Database Schema](#database-schema)
6. [Core Components](#core-components)

   * [Match Simulator](#match-simulator)
   * [Rating Updates](#rating-updates)
   * [Options Pricing & Lifecycle](#options-pricing--lifecycle)
   * [Digital Over/Under Bets](#digital-overunder-bets)
   * [Stock & Derivatives Trading](#stock--derivatives-trading)
7. [Web Interface](#web-interface)
8. [Mathematical Models](#mathematical-models)
9. [Usage](#usage)
10. [Contributing](#contributing)
11. [License](#license)

---

## Overview

ESL Trade is a simulation platform for a fictional European Super League where you can:

* **Simulate matches** using Poisson goal models and random events.
* **Track and evolve** club ratings via a stochastic process (GBM with drift).
* **Place in‑game bets**: moneyline, totals, spreads, BTTS, double‑chance, futures.
* **Trade club "shares"** in a stock‑exchange style market.
* **Trade vanilla options** (calls/puts) priced by Black–Scholes.
* **Trade digital options** (binary over/under bets) settling at discrete gameweek hooks.
* **Manage portfolios** across all market types.

## Features

* **Match Simulation** with Poisson-distributed goals, occasional random boosts or zeros (simulating upsets).
* **Rating Updates** based on match outcome drift calculations and Geometric Brownian Motion.
* **In-Game Sportsbook**: Moneyline, Totals, Spreads, Both Teams to Score, Double Chance, Single-Game Parlays, Futures.
* **Stock Exchange**: Buy/sell club equities, track portfolio value.
* **Vanilla Options**: Price and trade European calls and puts on club ratings.
* **Digital Options**: Binary Over/Under bets with automatic settlement each gameweek.
* **Portfolio Overview**: Realized/unrealized P\&L, equity curves, detailed holdings.

## Installation

1. Clone the repo:

   ```bash
   git clone https://github.com/your-org/esl-trade.git
   cd esl-trade
   ```
2. Create a virtualenv and install requirements:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Initialize the database:

   ```bash
   flask db upgrade   # or run SQL scripts under bfkt/sql/
   ```
4. Run the app:

   ```bash
   flask run
   ```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Project Structure

```
├── bfkt/
│   ├── models.py         # DB schema & helpers
│   ├── simulator.py      # Core match simulation & lifecycle functions
│   ├── options.py        # Vanilla option settlement
│   ├── obet.py           # Digital-over-under bet settlement
│   └── …
├── static/
│   ├── css/              # Stylesheets
│   └── images/           # Club logos & charts
├── templates/
│   ├── league.html       # Main standings & scheduler
│   ├── betzoom.html      # Detailed betting page
│   ├── options_portfolio.html
│   └── oneclub.html      # Single club dashboard
├── config.py
├── tester.py             # Utility functions (e.g. round_to_half)
└── README.md             # ← you are here
```

## Database Schema

* **participants**: Clubs, with `initial_rating`, `volatility`, `drift`.
* **schedule**: Fixture list, by `id`, `home`, `away`.
* **status**: Current `gameweek` & `gameno`.
* **matches**: Match results logged.
* **standings** / **points\_history**: League table & history.
* **equity** / **equity\_history**: Trading bankroll & portfolio valuations.
* **stock\_holdings**: Share volumes per club.
* **options\_holdings**: Vanilla options positions.
* **options\_bets**: Digital Over/Under bets.
* **ml\_bets**, **futures\_bets**: Sportsbook wagers.

## Core Components

### Match Simulator

* `simulate_match(home_rating, away_rating, scaling_factor=3, home_advantage=1.08)`

  1. Compute expected goals:
     $E_A = \frac{r_A}{r_A + r_B} \times \,3\times1.08, \quad E_B=\frac{r_B}{r_A + r_B}\times3$
  2. Sample goals: `A ~ Poisson(E_A)`, `B ~ Poisson(E_B)`.
  3. With small probability apply random boosts or zero-scoring upsets.

### Rating Updates

* `calculate_match_drifts(home_rating, away_rating, home_goals, away_goals)`:

  * Computes drift terms for winner/loser or draw via log-ratio and goal difference adjustments.

* **Geometric Brownian Motion**:
  $R_{t+Δ} = R_t \exp((μ - 0.5σ^2)Δ + σ√Δ\,Z)$

### Options Pricing & Lifecycle

* **Black–Scholes** for European calls/puts on club rating ×100:
  $d_{1,2} = \frac{\ln(S/K) + (r ± 0.5σ^2)T}{σ\sqrt{T}}$
  $C = SΦ(d_1) - K e^{-rT}Φ(d_2), \quad P = K e^{-rT}Φ(-d_2) - SΦ(-d_1)$

* **`update_options()`**: Recalculates `curr_premium` each game tick for open positions.

* **`settle_expirations(gw)`**: Settles and pays out in‑the‑money vanilla options at expiry.

### Digital Over/Under Bets

* **`settle_obets(gw)`**: For each expiring digital bet:

  1. Final underlying price = `initial_rating * 100`.
  2. Win if `Over` && final > strike, or `Under` && final < strike.
  3. Update `result` & credit bankroll on wins.

### Stock & Derivatives Trading

* **Stock Exchange**: Buy/sell club shares at `initial_rating * 100`.
* **Options**: Long calls/puts on underlying share price ×100 × contracts.
* **Digital Bets**: Binary options on point‑in‑time price.

## Web Interface

* **`league.html`**: Fixture simulation, standings, and moneyline bet form.
* **`betzoom.html`**: Full market blitz: ML, Totals, Spreads, Double Chance, BTTS.
* **`options_portfolio.html`**: Portfolio P\&L, active & expired vanilla/digital options.
* **`oneclub.html`**: Club dashboard: ratings chart, historical runs.

## Mathematical Models

1. **Poisson Goal Model**
2. **Drift Calculation** via log-ratios & goal differences
3. **Geometric Brownian Motion** rating evolution
4. **Black–Scholes PDE** for option premium
5. **Binary Settlement** at threshold strikes

## Usage

* **Simulate one match**: click "Simulate Match" on league page.
* **Simulate Rest of Gameweek**.
* **Place Bets**: click odds buttons → deposit stake → confirm.
* **Trade Clubs/Options**: navigate to Trade page.
* **View Portfolio**: Options Portfolio for real‑time P\&L.

## Contributing

1. Fork the repo.
2. Create a feature branch.
3. Commit & push.
4. Open a PR.

## License

MIT © M.K.Pritesh

