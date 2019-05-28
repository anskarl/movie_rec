# -*- coding: utf-8 -*-

from flask import request, jsonify, abort, Blueprint

from app import app, db, redis_pool
from app.api import common
from app.controller import MovieRecController
from app.models import user_schema, movie_schema, rating_schema


app_controller = MovieRecController(db,
                                     redis_pool=redis_pool,
                                     default_rating=app.config.get("DEFAULT_RATING"),
                                     top_n=app.config.get("TOP_N"))

api = Blueprint(name="v1", import_name="api")


@api.route('/', methods=['GET'])
def hello():
    return common.hello()


@api.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user_info = app_controller.get_user_info(user_id)

    return abort(404) if user_info is None else jsonify(user_schema.dump(user_info).data)


@api.route('/user', methods=['PUT'])
def add_user():
    content = request.json

    gender = None if content is None else content.get('gender')
    year_of_birth = None if content is None else content.get('year_of_birth')

    resulting_user = app_controller.add_user(gender, year_of_birth)

    return jsonify(user_schema.dump(resulting_user).data)


@api.route('/user/<int:user_id>', methods=['DELETE'])
def del_user(user_id):
    result = app_controller.delete_user(user_id)

    return abort(404) if result is None else jsonify({'user_id': user_id, 'msg': 'deleted'})


@api.route('/user/<int:user_id>/ratings/latest', methods=['GET'])
def get_user_ratings(user_id):
    limit = request.args.get('limit', 20)

    result = app_controller.get_user_ratings(user_id, limit)

    return abort(404) if result is None else jsonify({'user_id': user_id, 'limit': limit, 'ratings': result})


@api.route('/user/<int:user_id>/ratings/top', methods=['GET'])
def get_user_top_ratings(user_id):
    limit = request.args.get('limit', 20)

    result = app_controller.get_user_top_ratings(user_id, limit)

    return abort(404) if result is None else jsonify({'user_id': user_id, 'limit': limit, 'ratings': result})


@api.route('/movie/<int:movie_id>', methods=['GET'])
def get_movie_info(movie_id):
    result = app_controller.get_movie_info(movie_id)

    return abort(404) if result is None else jsonify(movie_schema.dump(result).data)


@api.route('/movies/top', methods=['GET'])
def get_top_movies():
    limit = request.args.get('limit', 100)
    rating_limit = request.args.get('rating_limit', None)

    result = app_controller.get_top_movies(limit, rating_limit)

    return abort(404) if result is None else jsonify(top_movies=result)


@api.route('/user/<int:user_id>/rating', methods=['PUT'])
def set_user_rating(user_id):
    content = request.json

    movie_id = int(content['movie_id'])
    rating = float(content['rating'])

    result = app_controller.set_movie_rating(user_id, movie_id, rating)

    return abort(404) if result is None else jsonify(rating_schema.dump(result).data)


@api.route('/user/<int:user_id>/rating', methods=['DELETE'])
def del_user_rating(user_id):
    content = request.json

    movie_id = int(content['movie_id'])

    deletion_result = app_controller.delete_movie_rating(user_id, movie_id)

    if deletion_result is None:
        return abort(404)
    else:
        return jsonify({'user_id': user_id, 'movie_id': movie_id, 'msg': 'deleted'})


@api.route('/user/<int:user_id>/watched', methods=['PUT', 'DELETE'])
def handle_user_watched(user_id):
    content = request.json

    movie_id = int(content['movie_id'])

    if request.method != 'PUT' and request.method != 'DELETE':
        # return with http error code 405 --- Method Not Allowed
        abort(405)

    set_watched = False if request.method == 'DELETE' else True

    result = app_controller.set_movie_watched(user_id, movie_id, set_watched=set_watched)

    return abort(404) if result is None else jsonify({'user_id': user_id, 'movie_id': movie_id, 'watched:': result})


@api.route("/user/<int:user_id>/recommendations", methods=['GET'])
def recommendations(user_id):
    result = app_controller.get_recommendations(user_id)

    if result is None:
        return abort(404)
    else:
        resulting_movies = [movie_schema.dump(m).data for m in result]
        return jsonify({'user_id': user_id, 'recommendations': resulting_movies})


