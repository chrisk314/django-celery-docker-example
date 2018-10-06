from celery.result import AsyncResult
from django.http import JsonResponse
from django.shortcuts import render

from .tasks import do_some_queries


def index(request):
    res = do_some_queries.delay()
    questions_count = res.get() if res.ready() else None
    context = (
        {"questions_count": questions_count}
        if questions_count is not None
        else {"task_id": res.task_id}
    )
    return render(request, "polls/index.html", context)


def check(request, task_id):
    task = AsyncResult(task_id)
    return JsonResponse({"questions_count": task.get() if task.ready() else None})
