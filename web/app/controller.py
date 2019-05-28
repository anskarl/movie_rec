# -*- coding: utf-8 -*-

import logging
import redis
from app.models import User, Rating, Movie, movie_schema
from sqlalchemy import func
from datetime import timezone, datetime


class MovieRecController:

    def __init__(self, db, redis_pool, default_rating, top_n):
        self.logger = logging.getLogger('Controller')
        self.db = db
        self.redis_client = redis.Redis(connection_pool=redis_pool)
        self.default_rating = default_rating
        self.top_n = top_n

    def get_user_info(self, user_id):
        self.logger.debug(f"Getting user info with user_id={user_id}")
        return self.db.session.query(User).get(user_id)

    def add_user(self, gender, year_of_birth):
        self.logger.debug(f"Adding user with gender = {str(gender)}, year_of_birth = {str(year_of_birth)}")

        user = User(gender=gender, year_of_birth=year_of_birth)

        self.db.session.add(user)
        self.db.session.commit()
        self.db.session.refresh(user)

        return user

    def delete_user(self, user_id):
        self.logger.debug(f"Deleting user with user_id={user_id}")
        user = User.query \
            .filter_by(user_id=user_id) \
            .one_or_none()

        if user is not None:
            self.db.session.delete(user)
            self.db.session.commit()
            return user_id
        else:
            return None

    def get_user_ratings(self, user_id, limit=None):
        self.logger.debug(f"Get ratings of user with user_id={user_id}")

        query = self.db.session \
            .query(Rating, Movie) \
            .join(Movie, Rating.movie_id == Movie.movie_id) \
            .filter(Rating.user_id == user_id) \
            .order_by(Rating.ts.desc())

        user_ratings = query.all() if limit is None else query.limit(limit).all()

        return self.convert_user_ratings(user_ratings)

    def get_user_top_ratings(self, user_id, limit=None):
        self.logger.debug(f"Get top ratings of user with user_id={user_id}")

        query = self.db.session \
            .query(Rating, Movie) \
            .join(Movie, Rating.movie_id == Movie.movie_id) \
            .filter(Rating.user_id == user_id) \
            .order_by(Rating.rating.desc(), Rating.ts.desc())

        user_ratings = query.all() if limit is None else query.limit(limit).all()

        return self.convert_user_ratings(user_ratings)

    def get_movie_info(self, movie_id):
        self.logger.debug(f"Getting movie info with movie_id={movie_id}")
        return self.db.session.query(Movie).get(movie_id)

    def get_top_movies(self, top_n, rating_limit=None):
        if rating_limit is not None:
            assert(0.5 < rating_limit < 5.0)

        self.logger.debug(f"Getting top {top_n} movies, with rating_limit = {str(rating_limit)}")

        avg_ratings = func.avg(Rating.rating).label("avg_ratings")
        count_users = func.count(Rating.user_id).label("count_users")

        rating_limit_filter = Rating.rating >= 3.5 if rating_limit is None else Rating.rating >= rating_limit

        top_n_rated = self.db.session \
            .query(avg_ratings, count_users, Rating.movie_id, Movie) \
            .join(Movie, Rating.movie_id == Movie.movie_id) \
            .filter(rating_limit_filter) \
            .group_by(Rating.movie_id, Movie) \
            .order_by(func.count(Rating.user_id).desc(), func.avg(Rating.rating).desc()) \
            .limit(top_n) \
            .all()

        result = [
            {
                'avg_rating': float(avg),
                'votes': int(votes),
                'movie': movie_schema.dump(m).data
             } for (avg, votes, r_mid, m,) in top_n_rated
        ]

        return result

    def set_movie_rating(self, user_id, movie_id, rating):
        self.logger.debug(f"User with user_id={user_id} rated with {rating} stars the movie with movie_id={movie_id}")
        assert(0.5 <= rating <= 5.0)

        rounded_rating = self.round_rating(rating)

        if self.db.session.query(User).get(user_id) is None or self.db.session.query(Movie).get(movie_id) is None:
            return None

        movie_rating = Rating(
            user_id=user_id,
            movie_id=movie_id,
            rating=rounded_rating,
            is_implicit=False,
            ts=datetime.now(tz=timezone.utc)
        )

        self.db.session.merge(movie_rating)
        self.db.session.commit()

        key = f"n_ratings_{user_id}"
        self.redis_client.incr(key)

        return movie_rating

    def delete_movie_rating(self, user_id, movie_id):
        self.logger.debug(f"Deleting rating of user with user_id={user_id} for movie with movie_id={movie_id}")
        movie_rating = Rating.query \
            .filter(Rating.user_id == user_id) \
            .filter(Rating.movie_id == movie_id) \
            .one_or_none()

        if movie_rating is None:
            return None
        else:
            self.db.session.delete(movie_rating)
            self.db.session.commit()

            key = f"n_ratings_{user_id}"
            self.redis_client.decr(key)

            return user_id, movie_id

    def set_movie_watched(self, user_id, movie_id, set_watched=True):
        self.logger.debug(f"User with user_id={user_id} watched movie with movie_id={movie_id}")

        if self.db.session.query(User).get(user_id) is None or self.db.session.query(Movie).get(movie_id) is None:
            return None

        if set_watched:

            key = 'm'+str(movie_id)+"#avg"
            avg_opt = self.redis_client.get(key)

            implicit_rating = float(avg_opt.decode("utf-8")) if avg_opt is not None else self.default_rating

            movie_rating = Rating(
                user_id=user_id,
                movie_id=movie_id,
                rating=implicit_rating,
                is_implicit=True,
                ts=datetime.now(tz=timezone.utc)
            )
            self.db.session.merge(movie_rating)
            self.db.session.commit()

            key = f"n_ratings_{user_id}"
            self.redis_client.incr(key)
        else:
            self.delete_movie_rating(user_id, movie_id)

        return set_watched

    def get_recommendations(self, user_id):
        """
        Gives the estimated recommendations for the specified user. The general idea
        is to provide recommendations that have been calculated by our recommendation
        algorithm.

        Please note that for in situations below:
            (1) We do not have recommendations for the user, due to user cold-start problem.
            (2) The number of recommendations that we have is less than the desired number (top-N),
            e.g., the user marked that he/she watched or rated one or more movies recently and our
            recommendation algorithm has not yet executed to give updated recommendations.

        This function will give the most popular movies and high-ranked as recommendations to the user.
        That is, movies that the users hasn't seen/ranked yet and have many voters, with top ratings (> 3).


        :param user_id: the id of the user to make movie recommendations
        :return: the top-N movie recommendations for the user, if the user exists, otherwise None
        """
        self.logger.debug(f"Getting movie recommendations for user with user_id={user_id}")

        # check if user exists
        if self.db.session.query(User).get(user_id) is None:
            return None

        def get_estimated_recommendations():
            """
            Gives the estimated recommendations for the specified user, if they exist.
            We also filter the results by what the user has been watched so far. Therefore,
            if the user watched/rated all the so far recommended movies, the the outcome
            of this function will be None, otherwise will give the estimated recommendations.

            :return: the estimated recommendations if they exist, otherwise None
            """

            key = 'u'+str(user_id)
            result = self.redis_client.get(key)

            if result is None:
                return None
            else:
                result_str = result.decode("utf-8")

                # get all pre-calculated estimated recommendations from redis
                top_movie_ids = [int(v) for v in result_str.split(";")]

                # make sure that the do not recommend any recently rated/watched movie
                recs = self.db.session\
                    .query(Rating.movie_id, Movie) \
                    .join(Movie, Rating.movie_id == Movie.movie_id) \
                    .filter(Rating.user_id != user_id) \
                    .filter(Movie.movie_id.in_(top_movie_ids))\
                    .limit(self.top_n)\
                    .all()

                # If we don't have any recommendation, return None (and thus fall-back to get_avg_recommendations)
                # Otherwise check whether the estimated recommendations are less than self.top_n, due to
                # recently watched/rated action(s) of the user.
                #  - In that case, we simply fill the missing values by taking from get_avg_recommendations()
                #  - otherwise, we just return the estimated recommendations :)
                if len(recs) == 0:
                    return None
                else:
                    estimated_recs = [m for (_, m) in recs]

                    if len(estimated_recs) < self.top_n:

                        self.logger.debug(f"Getting estimated recommendations extended with "
                                          f"{self.top_n - len(estimated_recs)} average top movie "
                                          f"recommendations for user with user_id={user_id}")

                        exclude_ids = [m.movie_id for m in estimated_recs]

                        additional_recs = get_avg_recommendations(
                            limit=self.top_n - len(estimated_recs),
                            exclude_movie_ids=exclude_ids
                        )
                        return estimated_recs.extend(additional_recs)
                    else:
                        self.logger.debug(f"Getting estimated recommendations extended user with user_id={user_id}")
                        return estimated_recs

        def get_avg_recommendations(limit=self.top_n, exclude_movie_ids=None):
            """
            In situations that we do not have any recommendation for the user, either due to cold-start issue or
            the users managed to mark as watched or rated all the currently recommended movies, we are falling back
            to give as recommendation the top movies (in terms of votes and avg rates) from our users

            :return: the top movies (in terms of votes and avg rates) from our users
            """

            self.logger.debug(f"Falling back to average top movie recommendations "
                              f"for user with user_id={user_id}, limit={limit} "
                              f"and exclude_movie_ids={exclude_movie_ids}")

            # Get the movie_ids that the user has rated or watched, in order
            # to exclude them later
            q_user_rated_movies = self.db.session \
                .query(Rating.movie_id) \
                .filter(Rating.user_id == user_id) \
                .subquery()

            # aggregation function for computing the average ratings of a movie
            avg_ratings = func.avg(Rating.rating).label("avg_ratings")

            # aggregation function for computing the total number of users that reated/watched a movie
            count_users = func.count(Rating.user_id).label("count_users")

            # Query for calculating the top movies w.r.t count_users and avg_ratings
            # therefore, we would like to have on a higher rank the movies having the
            # the greatest number of users and at the same time the highest possible rank
            q_top_movies = self.db.session \
                .query(avg_ratings, count_users, Rating.movie_id, Movie) \
                .join(Movie, Rating.movie_id == Movie.movie_id) \
                .filter(Rating.rating >= self.default_rating) \
                .group_by(Rating.movie_id, Movie) \
                .order_by(func.count(Rating.user_id).desc(), func.avg(Rating.rating).desc())

            # exclude movie ids from exclude_movie_ids, when is set
            q_top_movies if exclude_movie_ids is None else q_top_movies.filter(~Rating.movie_id.in_(exclude_movie_ids))

            # compute the actual query, with is composed of the previous ones,
            # filter out movies that the user watched and limit the results to the
            # desired top-N number of movies
            resulting_recommendations = q_top_movies\
                .outerjoin(q_user_rated_movies, Rating.movie_id == q_user_rated_movies.c.movie_id) \
                .filter(q_user_rated_movies.c.movie_id.is_(None))\
                .limit(limit)

            recs = [m for (_, _, _, m) in resulting_recommendations]
            return recs

        resulting_movies = get_estimated_recommendations()

        return get_avg_recommendations() if resulting_movies is None else resulting_movies

    @staticmethod
    def convert_user_ratings(user_ratings):
        result = [
            {
                'is_implicit': r.is_implicit,
                'rating': str(r.rating),
                'ts': str(r.ts),
                'movie': movie_schema.dump(m).data
            } for (r, m) in user_ratings
        ]

        return result

    @staticmethod
    def round_rating(rating):
        return round(rating * 2) / 2
