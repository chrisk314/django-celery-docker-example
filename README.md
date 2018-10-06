# Django Celery Docker Example
This is a minimal example demonstrating how to set up the components of a Django app with Celery
workers using Docker.

## Install

```
git clone git@github.com:chrisk314/django-celery-docker-example.git
cd django-celery-docker-example
virtualenv -p python3 venv
. .env
python -m pip install -r requirements.txt
```

## Run

Assuming you have `docker` and `docker-compose` installed on your system, the app can be run with
```
docker-compose up
```
