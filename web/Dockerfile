FROM python:3.6

RUN pip install --no-cache-dir requests==2.22.0 \
    && pip install --no-cache-dir scipy==1.1.0 \
    && pip install --no-cache-dir numpy==1.14.6 \
    && pip install --no-cache-dir Cython==0.28.5 \
    && pip install --no-cache-dir pandas==0.23.4 \
    && pip install --no-cache-dir flask==1.0.2 \
    && pip install --no-cache-dir psycopg2-binary==2.7.5 \
    && pip install --no-cache-dir Flask-SQLAlchemy==2.3 \
    && pip install --no-cache-dir Flask-Migrate==2.2.1 \
    && pip install --no-cache-dir alembic==0.8.5 \
    && pip install --no-cache-dir flask-marshmallow==0.9.0 \
    && pip install --no-cache-dir apscheduler==3.5.2 \
    && pip install --no-cache-dir redis==2.10.6 \
    && pip install --no-cache-dir backoff==1.6.0 \
    && pip install --no-cache-dir marshmallow-sqlalchemy==0.14.1 \
    && pip install --no-cache-dir scikit-surprise==1.0.6 \
    && pip install --no-cache-dir gunicorn==19.9.0


RUN mkdir -p /opt/movierec
WORKDIR /opt/movierec

COPY . /opt/movierec/

RUN curl 'https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh' -o wait-for-it.sh \
    && chmod +x wait-for-it.sh