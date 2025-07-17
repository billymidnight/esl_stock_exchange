CREATE TABLE options_holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT CHECK(type IN ('call', 'put')) NOT NULL,
    underlying TEXT NOT NULL,
    strike REAL NOT NULL,
    expiration_gw INTEGER NOT NULL,
    cost REAL NOT NULL,
    contracts INTEGER NOT NULL,
    expired BOOLEAN DEFAULT 0,
    curr_premium REAL,
    itm_otm TEXT,
    held_till_expiry BOOLEAN default 0,
    expired_underlying REAL,

    FOREIGN KEY (underlying) REFERENCES participants(name)
);

CREATE TABLE options_history (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT CHECK(type IN ('call', 'put')) NOT NULL,
    action TEXT CHECK(action IN ('buy', 'sell')) NOT NULL,
    underlying TEXT NOT NULL,
    strike REAL NOT NULL,
    underlying_price REAL NOT NULL,
    contracts INTEGER NOT NULL,
    premium REAL NOT NULL,
    gameweek_traded INTEGER NOT NULL,
    gameweek_expiry INTEGER NOT NULL,

    buy_gameweek INTEGER,
    premium_bought REAL,
    profit_made REAL,

    FOREIGN KEY (underlying) REFERENCES participants(name)
);

CREATE TABLE options_bets (
    obet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    obet_underlying VARCHAR(100) NOT NULL,        
    obet_type VARCHAR(10) CHECK(obet_type IN ('Over', 'Under')), 
    obet_strike REAL NOT NULL,                      
    obet_expiry INTEGER NOT NULL,                   
    obet_size REAL NOT NULL,                     
    obet_odds INTEGER NOT NULL,                   
    obet_potential_payout REAL NOT NULL,            
    obet_gw_placed INTEGER NOT NULL,                
    obet_placed_price REAL NOT NULL,
    result VARCHAR(10)                
);
