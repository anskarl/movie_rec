#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import io
import tempfile
import logging
import pandas as pd
import numpy as np
import time
import requests
import backoff
import csv
from dateutil.parser import parse
import sqlalchemy

log = logging.getLogger("dataset_loader")


@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=60)
def get_url(url):
    return requests.get(url)


def fetch_dataset():
    check_filenames = ['links.csv', 'ratings.csv']
    dataset_name = "ml-latest-small"
    temp_dir = tempfile.gettempdir()

    dataset_url = f"http://files.grouplens.org/datasets/movielens/{dataset_name}.zip"
    dataset_zip_file_path = os.path.join(temp_dir, dataset_name)
    dataset_path = os.path.join(os.path.curdir, dataset_name)

    def check_files(target_path):
        for filename in check_filenames:
            curr_path = os.path.join(target_path, filename)
            if not os.path.exists(curr_path):
                return False

        return True

    if check_files(dataset_path):
        log.info(f"Dataset exists in '{dataset_path}'")
        return dataset_path

    log.info(f"Fetching dataset from '{dataset_url}' to '{dataset_zip_file_path}'")

    req = requests.get(dataset_url)
    if req.status_code == 200:
        if req.content is None:
            log.error("Received empty dataset")
            raise IOError("Received empty dataset")
        else:
            zip_file = zipfile.ZipFile(io.BytesIO(req.content))
            for member in check_filenames:
                zip_file.extract(dataset_name + "/" + member, os.path.curdir)

            resulting_path = os.path.join(os.path.curdir, dataset_name)

            if check_files(resulting_path):
                return resulting_path
            else:
                raise IOError(f"Failed to verify the existence of required files: {','.join(check_filenames)}")
    else:
        log.error(f"Failed to download dataset from '{dataset_url}', got request code: {str(req.status_code)}")
        req.raise_for_status()


def load_ratings_users_df(dataset_path):
    start_time = time.time()

    ratings_df = pd.read_csv(os.path.join(dataset_path, "ratings.csv"),
                             sep=',',
                             engine='python',
                             encoding='ISO-8859-1',
                             skiprows=1,
                             names=['user_id', 'movie_id', 'rating', 'ts'],
                             dtype={"user_id": np.int32, "movie_id": np.int32, "rating": np.float32, "ts": np.int64})

    ratings_df["ts"] = pd.to_datetime(ratings_df["ts"], unit="s")

    unique_user_ids = ratings_df['user_id'].unique()
    users_df = pd.DataFrame(data={'user_id': unique_user_ids}, index=unique_user_ids)

    end_time = time.time()

    ratings_df.info()
    users_df.info()

    log.debug(f"Number of ratings: {len(ratings_df.index)}")
    log.debug(f"Number of users: {len(unique_user_ids)}")
    log.debug(f"load_ratings_users_df took {end_time-start_time} seconds")

    return ratings_df, users_df


def load_movies_df(dataset_path, api_key):

    def load_links_df(dataset_path):
        start_time = time.time()

        links_df = pd.read_csv(os.path.join(dataset_path, "links.csv"),
                               sep=',',
                               engine='python',
                               encoding="ISO-8859-1",
                               skiprows=1,
                               names=['movie_id', 'tmdb_id'],
                               usecols=[0, 2])

        end_time = time.time()

        log.debug(f"Number of movies: {len(links_df.index)}")
        log.debug(f"load_movies_df took {end_time-start_time} seconds")

        return links_df

    def create_enriched_movies_csv(links_df, movies_enriched_filepath, api_key):
        fieldnames = ['movie_id', 'title', 'year', 'genres', 'description']

        with open(movies_enriched_filepath, 'a') as movies_csv_file:
            writer = csv.DictWriter(movies_csv_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()

            for row in links_df.itertuples():
                movie_id = row.movie_id
                tmdb_id = row.tmdb_id

                result = get_url(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}")

                if result.status_code == 200:
                    json = result.json()
                    record = {
                        'movie_id': movie_id,
                        'title': json['title'],
                        'year': parse(json['release_date']).year,
                        'description': json['overview'],
                        'genres': "|".join([entry['name'] for entry in json['genres']])
                    }

                    log.info(f"Writing record for movie: with 'movie_id': {movie_id}, "
                             f"'title': {record['title']} and  'year': {record['year']}")
                    writer.writerow(record)
                else:
                    log.error(
                        f"Failed to gather information for movie with 'movie_id': {movie_id} and 'tmdb_id': {tmdb_id}")
                    writer.writerow({'movie_id': movie_id})

        return movies_enriched_filepath

    movies_enriched_filepath = os.path.join(dataset_path, 'movies_enriched.csv')

    if not os.path.exists(movies_enriched_filepath):
        links_df = load_links_df(dataset_path)
        create_enriched_movies_csv(links_df, movies_enriched_filepath, api_key)

    movies_df = pd.read_csv(movies_enriched_filepath,
                            sep=',', engine='python', encoding="ISO-8859-1", header=0,
                            dtype={"movie_id": np.int32, "title": np.str_, "year": np.int32,
                                   "description": np.str_, "genres": np.str_})

    movies_df.info()

    return movies_df


def write_to_db(db_engine, users_df, ratings_df, movies_df):
    start_time = time.time()

    log.info("Writing to table 'recommendation_users'")
    users_df \
        .to_sql('recommendation_users', con=db_engine.connect(), if_exists='append', index=False, chunksize=4096)

    log.info("Writing to table 'recommendation_ratings'")
    ratings_df \
        .to_sql('recommendation_ratings', con=db_engine.connect(), if_exists='append', index=False, chunksize=4096)

    log.info("Writing to table 'recommendation_movies'")
    movies_df \
        .to_sql('recommendation_movies', con=db_engine.connect(), if_exists='append', index=False, chunksize=4096)

    db_engine.connect().execute(
        "SELECT setval(pg_get_serial_sequence('recommendation_users', 'user_id'), coalesce(max(user_id)+1,1), false) "
        "FROM recommendation_users"
    )

    db_engine.connect().execute(
        "SELECT setval(pg_get_serial_sequence('recommendation_movies', 'movie_id'), coalesce(max(movie_id)+1,1), false) "
        "FROM recommendation_movies"
    )

    end_time = time.time()
    log.info(f"Loading time: {end_time-start_time}")


def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG,
                        stream=sys.stdout)

    # For TMDB_API_KEY see https://developers.themoviedb.org/3/getting-started/authentication
    # and https://www.themoviedb.org/login
    api_key = os.getenv("TMDB_API_KEY", None)

    if api_key == None:
        log.error("Please set the 'TMDB_API_KEY' environment variable. " \
        "For details visit 'https://developers.themoviedb.org/3/getting-started/authentication'")
        sys.exit(1)

    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME", "movierec")
    db_pass = os.getenv("DB_PASS", "movierec")
    db_port = os.getenv("DB_PORT", "5432")

    postgres_url = f"postgresql://postgres:{db_pass}@{db_host}:{db_port}/{db_name}"

    db_engine = sqlalchemy.create_engine(postgres_url)

    # Download original data set to a system's temporary directory and extract its contents
    dataset_path = fetch_dataset()
    ratings_df, users_df = load_ratings_users_df(dataset_path)
    movies_df = load_movies_df(dataset_path, api_key)

    write_to_db(db_engine, users_df, ratings_df, movies_df)


if __name__ == '__main__':
    main()
