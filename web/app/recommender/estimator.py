# -*- coding: utf-8 -*-
import pandas as pd
import logging
import time
import redis
from surprise import SVD, Dataset, Reader
from collections import defaultdict
from app.models import Rating


class Estimator:

    log = logging.getLogger(__name__)

    def __init__(self, db, redis_pool, redis_chunk_size, model_params, top_n):
        self.db = db
        self.redis_client = redis.Redis(connection_pool=redis_pool)
        self.redis_chunk_size = redis_chunk_size
        self.model_params = model_params
        self.top_n = top_n

    def load_dataset(self):
        _columns = ['user_id', 'movie_id', 'rating']

        start_time = time.time()
        df = pd.read_sql(Rating.__tablename__,
                         con=self.db.engine.connect(),
                         columns=_columns)

        result = Dataset.load_from_df(df[_columns], Reader(rating_scale=(0.5, 5.0)))

        end_time = time.time()

        self.log.info(f'Time spend loading dataset: {end_time - start_time} seconds')

        return result, df

    def train_model(self, data_set, params):
        self.log.debug(f"Training final model using whole data set with params: {params}")

        svd = SVD(**params)

        start_time = time.time()
        training_set = data_set.build_full_trainset()
        model = svd.fit(training_set)
        end_time = time.time()
        self.log.info(f'Time spend on training final model: {end_time - start_time} seconds')

        return model

    def get_top_n_predictions(self, data_set, model, n):
        predictions_start_time = time.time()

        anti_testset_start = time.time()
        self.log.debug("Constructing anti_testset...")
        test_set = data_set.build_full_trainset().build_anti_testset()
        anti_testset_end = time.time()
        self.log.debug(f'Total time spend on anti_testset construction: '
                      f'{anti_testset_end - anti_testset_start} seconds')

        predictions_start = time.time()
        self.log.debug("Calculating predictions...")
        predictions = model.test(test_set)
        predictions_end = time.time()
        self.log.debug(f'Total time spend on prediction calculations: '
                      f'{predictions_end - predictions_start} seconds')

        topn_start = time.time()
        self.log.debug("get-topN...")
        top_n_result = self.get_top_n(predictions, n)
        topn_end = time.time()
        self.log.debug(f'Total time spend on top-n: '
                      f'{topn_end - topn_start} seconds')

        predictions_end_time = time.time()
        self.log.debug(f'Total time spend on predictions of top-{n}: '
                      f'{predictions_end_time - predictions_start_time} seconds')

        return top_n_result

    def persist(self, resulting_predictions):
        start_time = time.time()

        with self.redis_client.pipeline() as pipe:
            pipe.multi()

            counter = 0
            for uid, user_ratings in resulting_predictions.items():
                key = 'u'+str(uid)
                value = str(";".join([str(iid) for (iid, _) in user_ratings]))
                pipe.set(key, value)
                counter += 1
                if counter % self.redis_chunk_size == 0:
                    pipe.execute()
                    pipe.multi()
                    self.log.debug(f'Current number of keys send to redis: {counter}')

            pipe.execute()
            self.log.debug(f'Total {counter} keys have been send to redis')
        end_time = time.time()

        self.log.info(f'Total time spend sending top-n to redis: {end_time - start_time} seconds')

    def recompute_recommendations(self):

        total_time_start = time.time()

        data, _ = self.load_dataset()
        model = self.train_model(data, self.model_params)
        resulting_predictions = self.get_top_n_predictions(data, model, self.top_n)
        self.persist(resulting_predictions)

        total_time_end = time.time()

        self.log.info(f"Total time of calculating latest recommendations (top-{self.top_n}): "
                      f"{total_time_end - total_time_start} seconds")

    @staticmethod
    def get_top_n(predictions, n=10):
        # First map the predictions to each user.
        top_n = defaultdict(list)
        for uid, iid, true_r, est, _ in predictions:
            top_n[uid].append((iid, est))

        # Then sort the predictions for each user and retrieve the k highest ones.
        for uid, user_ratings in top_n.items():
            user_ratings.sort(key=lambda x: x[1], reverse=True)
            top_n[uid] = user_ratings[:n]

        return top_n