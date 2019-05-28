# -*- coding: utf-8 -*-
import redis
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from config import Config
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
ma = Marshmallow(app)

redis_pool = redis.ConnectionPool(
    host=app.config.get("REDIS_HOST"),
    port=app.config.get("REDIS_PORT"),
    db=app.config.get("REDIS_DB")
)

from app import models, controller
from app.recommender.estimator import Estimator
from app.recommender.statistics import MovieStatistics

from app.api.v1.routes import api as routes_v1

app.register_blueprint(routes_v1, url_prefix='/api/v1')

estimator = Estimator(db,
                      redis_pool=redis_pool,
                      redis_chunk_size=app.config.get("REDIS_CHUNK_SIZE"),
                      model_params=app.config.get("MODEL_PARAMS"),
                      top_n=app.config.get("TOP_N"))

movie_stats = MovieStatistics(db,
                              redis_pool=redis_pool,
                              users_lower_limit=app.config.get("STAT_MOVIE_USERS_LOWER_LIMIT"),
                              redis_chunk_size=app.config.get("REDIS_CHUNK_SIZE"))


def trigger_recompute_recommendations():
    app.logger.info('Recomputing recommendations...')
    estimator.recompute_recommendations()


def trigger_recompute_movie_stats():
    app.logger.info('Recomputing movie statistics...')
    movie_stats.calc_rating_stats()


scheduler = BackgroundScheduler()
scheduler.add_job(trigger_recompute_recommendations, 'interval', minutes=15, next_run_time=datetime.now())
scheduler.add_job(trigger_recompute_movie_stats, 'interval', minutes=30, next_run_time=datetime.now())
scheduler.start()
