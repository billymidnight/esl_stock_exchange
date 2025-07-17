create table equity (
    equity real not null,
    bankroll real not null
);

insert into equity values (1000.0, 1000.0);

CREATE TABLE ratings_history (
    club_name VARCHAR(200) NOT NULL,
    gameweek INTEGER NOT NULL,
    rating REAL NOT NULL,
    PRIMARY KEY (club_name, gameweek),
    FOREIGN KEY (club_name) REFERENCES participants(name)
);

INSERT INTO ratings_history (club_name, gameweek, rating)
SELECT name, 0, initial_rating FROM participants;

CREATE TABLE stock_holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_name VARCHAR(200) NOT NULL,
    volume INTEGER NOT NULL,
    avg_cost REAL NOT NULL,
    FOREIGN KEY (club_name) REFERENCES participants(name)
);

INSERT INTO stock_holdings (club_name, volume, avg_cost)
SELECT name, 0, 0.0 FROM participants;


CREATE TABLE clubs_descs (
    club_name VARCHAR(200) PRIMARY KEY,
    description TEXT NOT NULL,
    FOREIGN KEY (club_name) REFERENCES participants(name)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gameweek INTEGER NOT NULL,
    club_name VARCHAR(200) NOT NULL,
    action TEXT CHECK(action IN ('buy', 'sell')) NOT NULL,
    volume_traded INTEGER NOT NULL,
    underlying_price REAL NOT NULL,
    FOREIGN KEY (club_name) REFERENCES participants(name)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gameweek INTEGER NOT NULL,
    club_name VARCHAR(200) NOT NULL,
    action TEXT CHECK(action IN ('buy', 'sell')) NOT NULL,
    volume_traded INTEGER NOT NULL,
    underlying_price REAL NOT NULL,
    FOREIGN KEY (club_name) REFERENCES participants(name)
);

CREATE TABLE equity_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gameweek INTEGER NOT NULL,
    gameno INTEGER NOT NULL,
    equity_value REAL NOT NULL
);
