# -*- coding: utf-8 -*-

import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True

    DB_HOST = os.getenv('DB_HOST', "localhost")
    DB_PORT = os.getenv('DB_PORT', "5432")
    DB_NAME = os.getenv('DB_NAME', "movierec")
    DB_USER = os.getenv('DB_USER', "postgres")
    DB_PASS = os.getenv('DB_PASS', "movierec")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    REDIS_CHUNK_SIZE = int(os.getenv('REDIS_CHUNK_SIZE', "1000"))
    REDIS_HOST = os.getenv('REDIS_HOST', "localhost")
    REDIS_PORT = int(os.getenv('REDIS_PORT', "6379"))
    REDIS_DB = int(os.getenv('REDIS_DB', "0"))
    DEFAULT_RATING = float(os.getenv('DEFAULT_RATING', "3.5"))
    TOP_N = int(os.getenv('TOP_N', "20"))
    STAT_MOVIE_USERS_LOWER_LIMIT = int(os.getenv('STAT_MOVIE_USERS_LOWER_LIMIT', "5"))

    MODEL_PARAMS = {
        'n_factors': int(os.getenv('MODEL_N_FACTORS', 50)),
        'n_epochs': int(os.getenv('MODEL_N_EPOCHS', 50)),
        'lr_all': float(os.getenv('MODEL_LR_ALL', 0.008)),
        'reg_all': float(os.getenv('MODEL_REG_ALL', 0.2))
    }


class ProductionConfig(Config):
    DEBUG = False


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True