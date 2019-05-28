# -*- coding: utf-8 -*-
import redis
import time
import logging
from app.models import Rating
from sqlalchemy import func


class MovieStatistics:

    log = logging.getLogger(__name__)

    def __init__(self, db, redis_pool, users_lower_limit, redis_chunk_size):
        self.redis_client = redis.Redis(connection_pool=redis_pool)
        self.users_lower_limit = users_lower_limit
        self.redis_chunk_size = redis_chunk_size
        self.db = db

    def calc_rating_stats(self):

        pg_start_time = time.time()
        avg_ratings_func = func.avg(Rating.rating).label("avg_ratings")
        count_users_func = func.count(Rating.user_id).label("count_users")

        result = self.db.session \
            .query(Rating.movie_id, count_users_func, avg_ratings_func) \
            .filter(Rating.is_implicit.is_(False)) \
            .group_by(Rating.movie_id) \
            .order_by(func.count(Rating.user_id).desc()) \
            .having(func.count(Rating.user_id) > self.users_lower_limit)\
            .all()

        pg_end_time = time.time()

        self.log.info(f'Total time spend computing movie statistics: {pg_end_time - pg_start_time} seconds')

        redis_start_time = time.time()

        with self.redis_client.pipeline() as pipe:
            pipe.multi()

            counter = 0
            for m_id, count_users, avg_ratings in result:
                key_counts = 'm'+str(m_id)+"#counts"
                value_counts = count_users

                key_avg = 'm'+str(m_id)+"#avg"
                value_avg = avg_ratings

                pipe.set(key_counts, value_counts)
                pipe.set(key_avg, value_avg)

                counter += 2
                if counter % self.redis_chunk_size == 0:
                    pipe.execute()
                    pipe.multi()
                    self.log.info(f'Current number of keys send to redis: {counter}')

            pipe.execute()
            self.log.info(f'Total {counter} keys have been send to redis')

        redis_end_time = time.time()

        self.log.info(f'Total time spend sending movie statistics to redis: {redis_end_time - redis_start_time} seconds')

