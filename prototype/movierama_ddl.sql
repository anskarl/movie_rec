create table if not exists recommendation_users
(
  user_id serial not null primary key,
  gender text default null,
  year_of_birth integer default null
);

alter table recommendation_users owner to postgres;


create table if not exists recommendation_ratings
(
  user_id integer not null,
  movie_id integer not null,
  rating double precision,
  is_implicit boolean not null default false,
  ts timestamp with time zone default now(),
  constraint recommendation_ratings_pkey
  primary key (user_id, movie_id)
);

alter table recommendation_ratings owner to postgres;


create table if not exists recommendation_movies
(
  movie_id serial not null primary key,
  title text,
  year integer,
  description text,
  genres text
);

alter table recommendation_movies owner to postgres;