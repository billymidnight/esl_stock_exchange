CREATE TABLE bankroll (
    curr_bankroll NUMERIC(10, 2) NOT NULL
);

insert into bankroll values (1000);

create table futures_bets (
    betid INTEGER PRIMARY KEY AUTOINCREMENT,
    horse varchar(200) not null,
    stake real not null,
    odds int not null,
    payout real not null,
    status varchar not null,
    winlose varchar,
    actualchamp varchar,
    CHECK (status in ('live', 'past'))
);

create table ml_bets (
    betid INTEGER PRIMARY KEY AUTOINCREMENT,
    gameid INTEGER,
    home varchar(200) not null,
    away varchar(200) not null,
    horse varchar(200) not null,
    stake real not null,
    odds int not null,
    payout real not null,
    status varchar not null,
    actualhome int,
    actualaway int,
    winlose varchar,
    CHECK (status in ('live', 'past'))
    CHECK (horse in ('home', 'away', 'draw'))
);
