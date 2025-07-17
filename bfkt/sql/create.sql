
CREATE TABLE participants (
    name varchar(200) not null primary key,
    filename varchar(200) not null,
    nation varchar(200) not null,
    city varchar(200) not null,
    drift numeric not null,
    volatility real not null,
    initial_rating real not null,
    gw_played BOOLEAN
);

CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    home varchar NOT NULL,
    away varchar NOT NULL,
    home_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL,
    FOREIGN KEY (home) REFERENCES participants(name),
    FOREIGN KEY (away) REFERENCES participants(name)
);

CREATE TABLE standings (
    name varchar(200) PRIMARY KEY,
    matches_played INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    goals_for INTEGER NOT NULL DEFAULT 0,
    goals_against INTEGER NOT NULL DEFAULT 0,
    goal_difference INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (name) REFERENCES participants(name)
);

CREATE TABLE noodds (
    noodds INTEGER not null
);
insert into noodds values (1);


CREATE TABLE points_history (
    name varchar(200) not null,
    gameweek INTEGER not null,
    points INTEGER not null,
    PRIMARY KEY (name, gameweek),
    FOREIGN KEY (name) REFERENCES participants(name)
);

INSERT INTO points_history (name, gameweek, points)
SELECT name, 0, 0 FROM participants;

