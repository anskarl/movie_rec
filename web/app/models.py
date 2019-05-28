# -*- coding: utf-8 -*-
from app import db, ma
from datetime import timezone, datetime


class Rating(db.Model):
    __tablename__ = 'recommendation_ratings'

    user_id = db.Column(db.Integer, primary_key=True, nullable=False)
    movie_id = db.Column(db.Integer, primary_key=True, nullable=False)
    rating = db.Column(db.Float, nullable=True)
    is_implicit = db.Column(db.Boolean, nullable=False, default=False)
    ts = db.Column(db.TIMESTAMP(timezone=True),
                   nullable=True,
                   default=datetime.now(tz=timezone.utc))

    def __repr__(self):
        return f'<Rating(user_id={self.user_id},' \
               f'movie_id={self.movie_id},' \
               f'rating={self.rating},' \
               f'is_implicit={self.is_implicit},' \
               f'ts={self.ts})>'


class RatingSchema(ma.ModelSchema):
    class Meta:
        model = Rating


rating_schema = RatingSchema()


class User(db.Model):
    __tablename__ = 'recommendation_users'

    user_id = db.Column(db.Integer,
                        db.Sequence(name="recommendation_users_user_id_seq", increment=1),
                        primary_key=True)
    gender = db.Column(db.Text)
    year_of_birth = db.Column(db.Integer)

    def __repr__(self):
        return f'<User(user_id={self.user_id},' \
               f'gender={self.gender},' \
               f'year_of_birth={self.age})>'


class UserSchema(ma.ModelSchema):
    class Meta:
        model = User


user_schema = UserSchema()


class Movie(db.Model):
    __tablename__ = 'recommendation_movies'

    movie_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.Text, nullable=False)
    year = db.Column(db.Integer, nullable=True)
    genres = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Movie(movie_id={self.movie_id}, ' \
               f'title={self.title},' \
               f'year={self.year},' \
               f'genres={self.genres})>'


class MovieSchema(ma.ModelSchema):
    class Meta:
        model = Movie


movie_schema = MovieSchema()

