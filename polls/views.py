import os
import stat
from tempfile import NamedTemporaryFile

from celery.result import AsyncResult
from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.encoding import smart_str

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


def download(request):
    dl_dir = os.path.join(settings.STATIC_ROOT, 'download')
    if not os.path.exists(dl_dir):
        os.makedirs(dl_dir)

    tmpfile = NamedTemporaryFile(dir=dl_dir, suffix='.txt', delete=False).name
    fname = os.path.basename(tmpfile)
    with open(tmpfile, 'w') as f:
        f.write('hello\n')

    if settings.PRODUCTION:
        response = HttpResponse(content_type='application/force-download')
        response['X-Accel-Redirect'] = f'/protected/{fname}'
        os.chmod(tmpfile, stat.S_IROTH)  # Ensure file is readable by nginx
    else:
        response = FileResponse(
            open(tmpfile, 'rb'), content_type='application/force-download'
        )

    response['Content-Disposition'] = f'attachment; filename={fname}'
    response['Content-Length'] = os.path.getsize(tmpfile)

    return response
