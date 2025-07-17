create table schedule (
    id integer primary key autoincrement,
    home varchar(200),
    away varchar(200),
    foreign key (home) references participants(name),
    foreign key (away) references participants(name),
    unique (home, away)
);

create table status (
    gameweek int default 1,
    gameno int default 0
);
insert into status values (1,0);