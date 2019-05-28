FROM postgres:10.5-alpine

ENV POSTGRES_DB movierec
ENV POSTGRES_PASSWORD movierec
COPY dump.sql /docker-entrypoint-initdb.d/

EXPOSE 5432