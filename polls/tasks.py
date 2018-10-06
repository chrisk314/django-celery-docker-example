import time

from .models import Question
from mysite.celery_app import app as celery_app


@celery_app.task
def do_some_queries():
    time.sleep(10)
    return Question.objects.count()


@celery_app.task
def query_every_five_mins():
    pass
