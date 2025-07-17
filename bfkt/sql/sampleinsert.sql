
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
    obet_placed_price REAL NOT NULL                
);


