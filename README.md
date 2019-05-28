# Project Description

MovieRec: a movie recommentation service.

The technology stack is composed of the following:

 - Python programming language
 - Flask micro-service framework
 - Uses scikit-surprise library for recommendation algorithms
 - Data manipulation using Pandas and SQLAlchemy
 - PostgreSQL database 
 - Redis in-memory data structure store
 - Gunicorn WSGI HTTP Server
 - Advanced Python Scheduler for scheduling tasks (e.g., for periodically updating the recommendations)
 - Docker and docker-compose
 
MovieRec is a micro-service that wraps-up a REST API on top of a recommendation engine (user-item collaborative filtering). 
 
  - The variant of the recommendation engine is a user-item collaborative filtering.
  - Internally, MovieRec uses the *SVD* algorithm, by [Simon Funk](http://sifter.org/~simon/journal/20061211.html). For details see the official [documentation of scikit-surprise](https://surprise.readthedocs.io/en/v1.0.6/matrix_factorization.html#surprise.prediction_algorithms.matrix_factorization.SVD).
  - Prototype of the *SVD* algorithm using the MovieLens dataset (tested on 100K ml-latest-small and 1M ml-1m datasets). For the sake of simplicity, the dataset that we are using in the main application is *100K ml-latest-small*. The prototype contains Python scripts for downloading, preparing and loading the dataset to PostgreSQL, as well as script for training the SVD algorithm (training/testing and hyper parameter tuning). 
  - Estimation and evaluation of the model is being performed using:

       - 3-fold cross-validation.
       - Hyper-parameter tuning using grid search ('n_factors': [10, 30, 50], 'n_epochs': [10, 30, 50], 'lr_all': [0.002, 0.005, 0.008, 0.01], and 'reg_all': [0.2, 0.4, 0.6, 0.8]).
       - RMSE and MAE for evaluation.
       - Choose parameters from the variant with the best RMSE score. The chosen parameters are then provided to the configuration of the production implementation.
  
  - PostgreSQL keeps user, ratings and movie information. 
  - Redis keeps the following information which is periodically or live updated:
  
      - The top-N recommentations of each user, as they have been computed by the SVD algorithm. The number of recommendations is configurable, default is 20. The computation is periodically triggered every 15 minutes.
      - Movie statistics, which are periodically computed (every 30 minutes).
          1. The average rating of each movie, which should be voted at least with M users (it is configurable, default is 5).
          2. For each movie, the count of users that rated/watched the movie.

  - The service supports both explicit and implicit ratings. When the explicit ratings are provided, they are directly stored to PostgreSQL. When the rating is not direclty given by the user and we only have the information that the user watched a movie, MovieRec performs the following:
      
      - Sets the average rating of the movie, if such value exists in Redis, otherwise
      - when average does not exists, MovieRec set 3.5 stars as a default rating of the movie.

  - To deal with user cold-start problem, that is when a new user appears and thus we do not know anything regarding his/her movie interests,
  MovieRec recommends the top movies that exists in the database. Specifically, this is a list of movies which are popular and high rated --- i.e., the count of users rated/watched and average rating, sorted in descending order.
  - Since the recommendations are periodically updated, it may be possible that within that period of time a user to mark as watched or rate a movie that is recommended. In such case the service will not re-recommend the same movie and will fill the missing one(s) by recommending top movies, like the solution for the cold-start problem, but by filtering out the movies that the user watched/rated.

With all the aforementioned features and the architecture of the service, MovieRec can continuously provide and periodically re-estimate recommendations, without downtime. It can handle situations like cold-start problem, as well as cases that the status of the user is being updated while the re-estimation hasn't been applied yet.


## Project structure

The tree below outlines the most important parts of the project structure:

```
.
├── README.md              # This markdown file
├── docker-compose.yml     # Docker compose configuration file for running MovieRec 
├── postgres               # Docker image for PostgreSQL with preloaded MovieLens dataset
├── prototype              # Python scripts for dataset downloading and preparation, as well as model training and hyper-parameter tunning
└── web                    # The source code of the MovieRec micro-service
    ├── Dockerfile         # Docker definitions of the MovieRec micro-service 
    ├── app
    │   ├── api            # The routes of the service REST API
    │   ├── controller.py  # The controller with all functionality behind the service REST API
    │   ├── models.py      # The database models
    │   └── recommender    # Contains the implementation of the recommender
    ├── config.py          # The configuration of the application
    ├── requirements.txt   # All library requirements of the project
    └── service.py         # Service initialization
```

## Run project using docker-compose

You can run locally the project you only need a docker installation with docker-compose. The project-provided docker-compose configuration (see `docker-compose.yml` file) sets up and links together MovieRec, Redis and PosgreSQL. PostgreSQL is being preloaded with MovieLens `ml-latest-small` dataset. MovieRec service is exposed locally to port 8000.

To start MovieRec:

```
docker-compose up
```

The first time docker-compose will build Postgres and MovieRec docker images. 

To rebuild the images:

```
docker-compose build
```

To rebuild a specific image of a service, e.g., MovieRec image:

```
docker-compose build movierec
```


## Configuration Parameters

All project configuration parameters are defined in `./web/config.py` and can be handled using their corresponding environment variables:

### PostgreSQL-related databse parameters

| Environment variable | Default value | Description  |
| -------------------- | ------------- | ------------ |
| DB_HOST              | localhost     | host name/IP |
| DB_PORT              | 5432          | port number  |
| DB_NAME              | movierec      | db name      |
| DB_USER              | postgres      | user name    |
| DB_PASS              | movierec      | password     |

### Redis-related parameters

| Environment variable | Default value | Description  |
| -------------------- | ------------- | ------------ |
| REDIS_CHUNK_SIZE     | 1000          | Number of commands to buffer when using pipelines (see [redis-py documentation](https://github.com/andymccurdy/redis-py#pipelines))|
| REDIS_HOST           | localhost     | host name of Redis |
| REDIS_PORT           | 6379          | connection port |

### MovieRec-related parameters

| Environment variable         | Default value | Description  |
| ---------------------------- | ------------- | ------------ |
| TOP_N                        | 20            | Default limit of top-n values |
| STAT_MOVIE_USERS_LOWER_LIMIT | 5             | Minimum number of users rated a movie to consider the calculation of movie statistics (see 'web/app/recommender/statistics.py') |
| MODEL_N_FACTORS              | 50            | The number of factors of the SVD model
| MODEL_N_EPOCHS               | 50            | The number of iteration of the SGD procedure
| MODEL_LR_ALL                 | 0.008         | The learning rate for all parameters
| MODEL_REG_ALL                | 0.2           | The regularization term for all parameters.

## REST API and examples

#### Get user info (GET /api/v1/user/<int:user_id>)

For example get information for user with id '10':

```
curl -X GET http://127.0.0.1:8000/api/v1/user/10
```

#### Add a new user (ADD /api/v1/user)

Add a new user (male, with year of birth 1982):

```
curl -X PUT -H 'Content-Type: application/json' http://127.0.0.1:8000/api/v1/user -d '{ "gender": "M", "year_of_birth": "1982" }'
```

The resulting response is:
```
{
    "gender": "M",
    "user_id": 611,
    "year_of_birth": 1982
}
```
#### Delete a user (DELETE /api/v1/user/<int:user_id>)

Delete user with id '611':

```
curl -X DELETE  http://127.0.0.1:8000/api/v1/user/611 
```

The resulting response is:

```
{
    "msg": "deleted",
    "user_id": 611
}
```

#### Get top ratings of a user (GET /api/v1/user/<int:user_id>/ratings/top)

For example, get the top 20 (default) ratings of user with id '40'

```
curl -X GET 'http://127.0.0.1:8000/api/v1/user/40/ratings/top
```

You can optionally set a limit, e.g., limit=5 to get the top-5:

```
curl -X GET 'http://127.0.0.1:8000/api/v1/user/40/ratings/top?limit=5'
```

A fragment of the example response is given below:

```
{
    "limit": "5",
    "user_id": 40,
    "ratings": [
        {
            "is_implicit": false,
            "movie": {
                "description": "A gathering of friends. A gift of love. A celebration of life.",
                "genres": "Drama",
                "movie_id": 685,
                "title": "It's My Party",
                "year": 1996
            },
            "rating": "5.0",
            "ts": "1996-05-14 07:54:02+00:00"
        },
        {
            "is_implicit": false,
            "movie": {
                "description": "After World War II, Antonia and her daughter, Danielle, go back to their Dutch hometown, where Antonia's late mother has bestowed a small farm upon her. There, Antonia settles down and joins a tightly-knit but unusual community. Those around her include quirky friend Crooked Finger, would-be suitor Bas and, eventually for Antonia, a granddaughter and great-granddaughter who help create a strong family of empowered women.",
                "genres": "Drama|Comedy",
                "movie_id": 82,
                "title": "Antonia's Line",
                "year": 1995
            },
            "rating": "5.0",
            "ts": "1996-05-14 07:49:11+00:00"
        },
        ...
```

#### Get the latest ratings of a user (GET /api/v1/user/<int:user_id>/ratings/latest)

For example, get latest 20 (default) ratings of user with id '50'. 


```
curl -X GET 'http://127.0.0.1:8000/api/v1/user/50/ratings/latest
```

You can optionally set a limit, e.g., limit=5 to get the top-5:

```
curl -X GET 'http://127.0.0.1:8000/api/v1/user/50/ratings/latest?limit=5'
```

The results are sorted by timestamp in descending order and rating also in descending order. A fragment of the example response is given below:

```
{
  "limit": "5",
  "ratings": [
    {
      "is_implicit": false,
      "movie": {
        "description": "While the Civil War rages between the Union and the Confederacy, three men â a quiet loner, a ruthless hit man and a Mexican bandit â comb the American Southwest in search of a strongbox containing $200,000 in stolen gold.",
        "genres": "Western",
        "movie_id": 1201,
        "title": "The Good, the Bad and the Ugly",
        "year": 1966
      },
      "rating": "4.0",
      "ts": "2018-09-13 20:20:06+00:00"
    },
    {
      "is_implicit": false,
      "movie": {
        "description": "Orchestra Rehearsal (Italian: Prova d'orchestra) is a 1978 Italian film directed by Federico Fellini. It follows an Italian orchestra as the members go on strike against the conductor. The film was shown out of competition at the 1979 Cannes Film Festival. Considered by some to be underrated Orchestra Rehearsal was the last collaboration between composer Nino Rota and Fellini, due to Rota's death in 1979.",
        "genres": "Drama",
        "movie_id": 46862,
        "title": "Orchestra Rehearsal",
        "year": 1978
      },
      "rating": "3.5",
      "ts": "2018-08-13 16:47:38+00:00"
    },
        ...
```
#### Get movie info (GET /api/v1/movie/<int:movie_id>)

For example, get info for movie with id '1193'

```
curl -X GET http://127.0.0.1:8000/api/v1/movie/1193
```

Example response:

```
{
    "description": "While serving time for insanity at a state mental hospital, implacable rabble-rouser, Randle Patrick McMurphy inspires his fellow patients to rebel against the authoritarian rule of head nurse, Mildred Ratched.",
    "genres": "Drama",
    "movie_id": 1193,
    "title": "One Flew Over the Cuckoo's Nest",
    "year": 1975
}
```

#### Get top movies (GET /api/v1/movies/top)

Get the most popular and highly rated movies. Sorted by the number of users that watched/rate the move and the rate number, in descending order.

For example get the 100 most popular movies:

```
curl -X GET 'http://127.0.0.1:8000/api/v1/movies/top'
```

You can also provide some custom limit, e.g., limit=10:
```
curl -X GET 'http://127.0.0.1:8000/api/v1/movies/top?limit=10'
```

A fragment of the example response is given below:

```
{
    "top_movies": [
        {
            "avg_rating": 4.58823529411765,
            "movie": {
                "description": "Framed in the 1940s for the double murder of his wife and her lover, upstanding banker Andy Dufresne begins a new life at the Shawshank prison, where he puts his accounting skills to work for an amoral warden. During his long stretch in prison, Dufresne comes to be admired by the other inmates -- including an older prisoner named Red -- for his integrity and unquenchable sense of hope.",
                "genres": "Drama|Crime",
                "movie_id": 318,
                "title": "The Shawshank Redemption",
                "year": 1994
            },
            "votes": 289
        },
        {
            "avg_rating": 4.44202898550725,
            "movie": {
                "description": "A man with a low IQ has accomplished great things in his life and been present during significant historic eventsâ\u0080\u0094in each case, far exceeding what anyone imagined he could do. But despite all he has achieved, his one true love eludes him. â\u0080\u009cForrest Gumpâ\u0080\u009d is the story of a man who rises above his challenges and who proves that determination, courage, and love are more important than ability.",
                "genres": "Comedy|Drama|Romance",
                "movie_id": 356,
                "title": "Forrest Gump",
                "year": 1994
            },
            "votes": 276
        },
        ...
```

#### Add a user's rating (PUT /api/v1/user/<int:user_id>/rating)

For example rate with 3.5 stars movie with id '251' for user with id '30':

```
curl -X PUT -H 'Content-Type: application/json' http://127.0.0.1:8000/api/v1/user/30/rating  -d '{ "movie_id": 251, "rating": 3.5 }'
```

Example response:
```
{
    "is_implicit": false,
    "movie_id": 251,
    "rating": 3.5,
    "ts": "2018-09-30T14:55:20.158518+00:00",
    "user_id": 30
}
```

Please note that if the given rating is not normalized per half point from 0.0 to 5.0 the service will convert it to the nearest one. For example, if given rating is 3.8, the system will convert it to 4.0. 


#### Remove a user's rating (DELETE /api/v1/user/<int:user_id>/rating)

For example delete rating of movie with id '251' for user with id '30':

```
curl -X DELETE -H 'Content-Type: application/json' http://127.0.0.1:8000/api/v1/user/30/rating -d '{ "movie_id": 251 }'
```

Example response:

```
{
    "movie_id": 251,
    "msg": "deleted",
    "user_id": 30
}
```

#### Set movie watched (PUT /api/v1/user/<int:user_id>/watched)

For example set that user with id '60' watched movie with id '261':

```
curl -X PUT -H 'Content-Type: application/json' http://127.0.0.1:8000/api/v1/user/60/watched -d '{"movie_id": 261}'
```

Example response:

```
{
    "movie_id": 261,
    "user_id": 60,
    "watched:": true
}
```

#### Remove movie watched (DELETE /api/v1/user/<int:user_id>/watched)

For example delete that user with id '60' has watched movie with id '261':

```
curl -X DELETE -H 'Content-Type: application/json' http://127.0.0.1:8000/api/v1/user/60/watched -d '{ "movie_id": 261 }'
```

Example response:

```
{
    "movie_id": 261,
    "user_id": 60,
    "watched:": false
}
```

#### Get recommendations for a user (GET /api/v1/user/<int:user_id>/recommendations)

Get the top-N (default is 20) recommendations for a user. For example, get the recommendations
of user with id '51':

```
curl -X GET http://127.0.0.1:8000/api/v1/user/51/recommendations 
```

A fragment of the example response is given below:

```
{
    "user_id": 51,
    "recommendations": [
        {
            "description": "Framed in the 1940s for the double murder of his wife and her lover, upstanding banker Andy Dufresne begins a new life at the Shawshank prison, where he puts his accounting skills to work for an amoral warden. During his long stretch in prison, Dufresne comes to be admired by the other inmates -- including an older prisoner named Red -- for his integrity and unquenchable sense of hope.",
            "genres": "Drama|Crime",
            "movie_id": 318,
            "title": "The Shawshank Redemption",
            "year": 1994
        },
        {
            "description": "A man with a low IQ has accomplished great things in his life and been present during significant historic eventsâ\u0080\u0094in each case, far exceeding what anyone imagined he could do. But despite all he has achieved, his one true love eludes him. â\u0080\u009cForrest Gumpâ\u0080\u009d is the story of a man who rises above his challenges and who proves that determination, courage, and love are more important than ability.",
            "genres": "Comedy|Drama|Romance",
            "movie_id": 356,
            "title": "Forrest Gump",
            "year": 1994
        },
        {
            "description": "A burger-loving hit man, his philosophical partner, a drug-addled gangster's moll and a washed-up boxer converge in this sprawling, comedic crime caper. Their adventures unfurl in three stories that ingeniously trip back and forth in time.",
            "genres": "Thriller|Crime",
            "movie_id": 296,
            "title": "Pulp Fiction",
            "year": 1994
        },
        ...
```