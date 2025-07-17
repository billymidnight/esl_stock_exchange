create table champions (
    year integer primary key,
    winner varchar(200) not null,
    foreign key (winner) REFERENCES participants(name)
);

create table year (
    year integer
);

insert into year values (1930);

create table centralunit (
    year integer NOT NULL,
    home varchar NOT NULL,
    away varchar NOT NULL,
    home_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL
)