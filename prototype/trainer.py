# -*- coding: utf-8 -*-

import logging
import pandas as pd
import tempfile
import os
from surprise import SVD
from surprise import Dataset, Reader
from surprise.model_selection import GridSearchCV
import time
import sys
from collections import defaultdict
import redis

pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
redis_client = redis.Redis(connection_pool=pool)

log = logging.getLogger("trainer")


def load_dataset():
    temp_dir = tempfile.gettempdir()+os.sep
    dataset_name = "ml-latest-small"
    dataset_path = temp_dir+dataset_name

    input_dataset_path = os.path.join(dataset_path, "ratings.csv")

    start_time = time.time()
    df = pd.read_csv(input_dataset_path,
                     sep=',',
                     engine='python',
                     encoding='latin-1',
                     header=1,
                     names=['user_id', 'movie_id', 'rating', 'timestamp'])\
        .drop(columns=['timestamp'])

    result = Dataset.load_from_df(df[['user_id', 'movie_id', 'rating']], Reader(rating_scale=(0.5, 5.0)))

    end_time = time.time()

    log.info(f'Time spend loading dataset: {end_time - start_time} seconds')
    return result, df


def find_best_params(data_set, cv=3, param_grid=None):

    if param_grid is None:
        param_grid = {
            'n_factors': [10, 30, 50],
            'n_epochs': [10, 30, 50],
            'lr_all': [0.002, 0.005, 0.008, 0.01],
            'reg_all': [0.2, 0.4, 0.6, 0.8]
        }

    log.info(f'Performing Grid Search: {param_grid}')

    gs = GridSearchCV(SVD, param_grid=param_grid, measures=['rmse', 'mae'], cv=cv, n_jobs=4, joblib_verbose=2)
    start_time = time.time()
    gs.fit(data_set)
    end_time = time.time()
    log.info(f'Time spend on Grid Search: {end_time - start_time}')

    log.info(f"Best RMSE score: {gs.best_score['rmse']} with params: {gs.best_params['rmse']}")
    log.info(f"Best MAE score: {gs.best_score['mae']} with params: {gs.best_params['mae']}")

    return gs.best_params['rmse'], gs.best_params['mae']


def train_model_final(data_set, params):
    log.info(f"Training final model using whole data set with params: {params}")

    svd = SVD(**params)

    start_time = time.time()
    training_set = data_set.build_full_trainset()
    model = svd.fit(training_set)
    end_time = time.time()
    log.info(f'Time spend on training final model: {end_time - start_time}')

    return model


def get_top_n(predictions, n):

    # First map the predictions to each user.
    top_n = defaultdict(list)
    for uid, iid, true_r, est, _ in predictions:
        top_n[uid].append((iid, est))

    # Then sort the predictions for each user and retrieve the k highest ones.
    for uid, user_ratings in top_n.items():
        user_ratings.sort(key=lambda x: x[1], reverse=True)
        top_n[uid] = user_ratings[:n]

    return top_n


def get_top_n_predictions(data_set, model, n=10):
    anti_testset_start = time.time()
    log.info("Constructing anti_testset...")
    test_set = data_set.build_full_trainset().build_anti_testset()
    anti_testset_end = time.time()
    log.info(f'Total time spend on anti_testset construction: {anti_testset_end - anti_testset_start} seconds')

    predictions_start = time.time()
    log.info("Calclulating predictions...")
    predictions = model.test(test_set)
    predictions_end = time.time()
    log.info(f'Total time spend on prediction calculations: {predictions_end - predictions_start} seconds')

    topn_start = time.time()
    log.info("get-topN....")
    top_n_result = get_top_n(predictions, n)
    topn_end = time.time()
    log.info(f'Total time spend on top-n: {topn_end - topn_start} seconds')

    return top_n_result


def persist(resulting_predictions):
    start_time = time.time()

    with redis_client.pipeline() as pipe:
        pipe.multi()

        counter = 0
        for uid, user_ratings in resulting_predictions.items():
            key = 'u'+str(uid)
            value = str(";".join([str(iid) for (iid, _) in user_ratings]))
            pipe.set(key, value)
            counter += 1
            if counter % 1000 == 0:
                pipe.execute()
                log.info(f'Current number of keys send to redis: {counter}')
                pipe.multi()

        pipe.execute()
        log.info(f'Total {counter} keys have been send to redis')
    end_time = time.time()

    log.info(f'Total time spend sending top-n to redis: {end_time - start_time} seconds')


if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG,
                        stream=sys.stdout)
    total_start_time = time.time()
    data, df = load_dataset()

    best_rmse_params, best_mae_params = find_best_params(data)
    #best_rmse_params = {'n_factors': 50, 'n_epochs': 50, 'lr_all': 0.008, 'reg_all': 0.2}
    model = train_model_final(data, best_rmse_params)

    total_end_time = time.time()
    log.info(f'Total time spend on model estimation: {total_end_time - total_start_time} seconds')

    predictions_start_time = time.time()
    resulting_predictions = get_top_n_predictions(data, model, n=10)
    predictions_end_time = time.time()
    log.info(f'Total time spend on predictions of top-n: {predictions_end_time - predictions_start_time} seconds')

    persist(resulting_predictions)
