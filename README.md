# Django Celery Docker Example

This is a minimal example demonstrating how to set up the components of a Django app behind an Nginx
proxy with Celery workers using Docker.

## This repo is now archived
Seems like this repo still attracts a lot of views despite being very old! I am not maintaining this
repo. It was originally created as an example to illustrate some basic docker concepts to colleagues.
Some of the details are probably out of date by now. I no longer use Django. FastAPI or Golang is my
go to these days.

## Install

```bash
git clone git@github.com:chrisk314/django-celery-docker-example.git
cd django-celery-docker-example
virtualenv -p python3 venv
source venv/bin/activate
export SECRET_KEY=app-secret-key
python3 -m pip install -U pip && python3 -m pip install -r requirements.txt
```

## Run

To run the app, `docker` and `docker-compose` must be installed on your system. For installation
instructions refer to the Docker [docs](https://docs.docker.com/compose/install/).

#### Compose
The app can be run in development mode using Django's built in web server simply by executing

```bash
docker-compose up
```

To remove all containers in the cluster use

```bash
docker-compose down
```

To run the app in production mode, using gunicorn as a web server and nginx as a proxy, the
corresponding commands are

```bash
docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml up
docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml down
```

#### Swarm
It's also possible to use the same compose files to run the services using docker swarm. Docker
swarm enables the creation of multi-container clusters running in a multi-host environment with
inter-service communication across hosts via overlay networks.

```bash
docker swarm init --advertise-addr 127.0.0.1:2377
docker stack deploy -c docker-compose.yaml -c docker-compose.prod.yaml proj
```

It should be noted that the app will not be accessible via `localhost` in Chrome/Chromium. Instead
use `127.0.0.1` in Chrome/Chromium.

To bring down the project or _stack_ and remove the host from the swarm

```bash
docker stack rm proj
docker swarm leave --force
```

## Description

The setup here defines distinct development and production environments for the app. Running
the app using Django's built in web server with `DEBUG=True` allows for quick and easy development;
however, relying on Django's web server in a production environment is discouraged in the Django
[docs](https://docs.djangoproject.com/en/2.1/ref/django-admin/#runserver) for security reasons.
Additionally, serving large files in production should be handled by a proxy such as nginx to
prevent the app from blocking.

&nbsp;
### Compose files
Docker compose files allow the specification of complex configurations of multiple inter-dependent
services to be run together as a cluster of docker containers. Consult the excellent docker-compose
[reference](https://docs.docker.com/compose/compose-file/) to learn about the many different
configurable settings. Compose files are written in [`.yaml`](http://yaml.org/) format and feature three
top level keys: services, volumes, and networks. Each service in the services section defines a
separate docker container with a configuration which is independent of other services.

##### base compose
To support different environments, several docker-compose files are used in
this project. The base compose file, [`docker-compose.yaml`](./docker-compose.yaml), defines all
service configuration common to both the development and production environments. Here's the content
of the `docker-compose.yaml` file

```YAML
# docker-compose.yaml

version: '3.4'

services:

  rabbitmq:
    container_name: rabbitmq
    hostname: rabbitmq
    image: rabbitmq:latest
    networks:
      - main
    ports:
      - "5672:5672"
    restart: on-failure

  postgres:
    container_name: postgres
    hostname: postgres
    image: postgres:latest
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=postgres
    networks:
      - main
    ports:
      - "5432:5432"
    restart: on-failure
    volumes:
      - postgresql-data:/var/lib/postgresql/data

  app:
    build: .
    command: sh -c "wait-for postgres:5432 && python manage.py collectstatic --no-input && python manage.py migrate && gunicorn mysite.wsgi -b 0.0.0.0:8000"
    container_name: app
    depends_on:
      - postgres
      - rabbitmq
    expose:
      - "8000"
    hostname: app
    image: app-image
    networks:
      - main
    restart: on-failure

  celery_worker:
    command: sh -c "wait-for rabbitmq:5672 && wait-for app:8000 -- celery -A mysite worker -l info"
    container_name: celery_worker
    depends_on:
      - app
      - postgres
      - rabbitmq
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '0.50'
          memory: 50M
        reservations:
          cpus: '0.25'
          memory: 20M
    hostname: celery_worker
    image: app-image
    networks:
      - main
    restart: on-failure

  celery_beat:
    command: sh -c "wait-for rabbitmq:5672 && wait-for app:8000 -- celery -A mysite beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler"
    container_name: celery_beat
    depends_on:
      - app
      - postgres
      - rabbitmq
    hostname: celery_beat
    image: app-image
    networks:
      - main
    restart: on-failure

networks:
  main:

volumes:
  postgresql-data:
```

###### _services_
This compose file defines five distinct services which each have a single responsibility (this is
the core philosophy of Docker): `app`, `postgres`, `rabbitmq`, `celery_beat`, and `celery_worker`.
The `app` service is the central component of the Django application responsible for processing user
requests and doing whatever it is that the Django app does. The Docker image `app-image` used by the
`app` service is built from the [`Dockerfile`](./Dockerfile) in this project. For details of how to
write a `Dockerfile` to build a container image, see the
[docs](https://docs.docker.com/engine/reference/builder/). The `postgres` service provides the
database used by the Django app and `rabbitmq` acts as a message broker, distributing tasks in the
form of messages from the app to the celery workers for execution. The `celery_beat` and
`celery_worker` services handle scheduling of periodic tasks and asynchronous execution of tasks
defined by the Django app respectively and are discussed in detail [here](#celery-config).

###### _networks_
Because all the services belong to the same `main` network defined in the `networks` section, they
are able to find each other on the network by the relevant `hostname` and communicate with each other on
any ports exposed in the service's `ports` or `expose` sections. The difference between `ports` and
`expose` is simple: `expose` exposes ports only to linked services on the same network; `ports` exposes ports
both to linked services on the same network and to the host machine (either on a random host port or on a
specific host port if specified).

```YAML
services:
  app:
    expose:
      - "8000"
    networks:
      - main

networks:
  main:
```

**Note**: When using the `expose` or `ports` keys, **always** specify the ports using strings
enclosed in quotes, as ports specified as numbers can be interpreted incorrectly when the compose
file is parsed and give unexpected (and confusing) results!

###### _volumes_
To persist the database tables used by the `app` service between successive invocations of the
`postgres` service, a persistent volume is mounted into the `postgres` service using the `volumes`
keyword. The volume `postgresql-data` is defined in the `volumes` section with the default options.
This means that Docker will automatically create and manage this persistent volume within the Docker
area of the host filesystem.

```YAML
services:
  postgres:
    volumes:
      - postgresql-data:/var/lib/postgresql/data

volumes:
  postgresql-data:
```

**Warning**: be careful when bringing down containers with persistent volumes not to use the `-v`
argument as this will delete persistent volumes! In other words, only execute `docker-compose down
-v` if you want Docker to delete all named and anonymous volumes.

##### override compose
When executing `docker-compose up`, a
[`docker-compose.override.yaml`](./docker-compose.override.yaml) file, if present, automatically
overrides settings in the base compose file. It is common to use this feature to specify development
environment specific configuration. Here's the content of the `docker-compose.override.yaml` file

```YAML
# docker-compose.override.yaml

version: '3.4'

services:

  app:
    command: sh -c "wait-for postgres:5432 && python manage.py migrate && python manage.py runserver 0.0.0.0:8000"
    ports:
      - "8000:8000"
    volumes:
      - .:/usr/src/app
```

The command for the `app` container has been overridden to use Django's `runserver` command to run
the web server; also, it's not necessary to run `collectstatic` in the dev environment so this is
dropped from the command. Port 8000 in the container has been mapped to port 8000 on the host so
that the app is accessible at `localhost:8000` on the host machine. To ensure code changes trigger a
server restart, the app source directory has been mounted into the container in the `volumes`
section. Bear in mind that host filesystem locations mounted into Docker containers running with the
root user are at risk of being modified/damaged so care should be taken in these instances.

##### production compose
Here's the content of the `docker-compose.prod.yaml` file which specifies additional service
configuration specific to the production environment

```YAML
# docker-compose.prod.yaml

version: '3.4'

services:

  app:
    environment:
      - DJANGO_SETTINGS_MODULE=mysite.settings.production
      - SECRET_KEY
    volumes:
      - static:/static

  nginx:
    container_name: nginx
    command: wait-for app:8000 -- nginx -g "daemon off;"
    depends_on:
      - app
    image: nginx:alpine
    networks:
      - main
    ports:
      - "80:80"
    restart: on-failure
    volumes:
      - ${PWD}/nginx.conf:/etc/nginx/nginx.conf
      - ${PWD}/wait-for:/bin/wait-for
      - static:/var/www/app/static

volumes:
  static:
```

An additional `nginx` service is specified to act as a proxy for the app, which is discussed in
detail [here](#nginx). Changes to the `app` service include: a production specific Django settings
module, a secret key sourced from the environment, and a persistent volume for static files which is
shared with the `nginx` service. Importantly, the `nginx` service must use the `wait-for` script
(discussed [below](#service-dependency-and-startup-order)) to ensure that the app is ready to accept
requests on port 8000 before starting the nginx daemon.  Failure to do so will mean that the app is
not accessible by nginx without restarting the `nginx` service once the `app` service is ready.

&nbsp;
### Service dependency and startup order
The compose file allows dependency relationships to be specified between containers using the
`depends_on` key. In the case of this project, the `app` service depends on the `postgres` service
(to provide the database) as well as the `rabbitmq` service (to provide the message broker). In
practice this means that when running `docker-compose up app`, or just `docker-compose up`, the
`postgres` and `rabbitmq` services will be started if they are not already running before the `app`
service is started.

```YAML
services:
  app:
    depends_on:
      - postgres
      - rabbitmq
```

Unfortunately, specifying `depends_on` is not sufficient on its own to ensure the correct/desired
start up behaviour for the service cluster. This is because Docker starts the `app` service once
both the `postgres` and `rabbitmq` services have _started_; however, just because a service has
_started_ does not guarantee that it is _ready_. It is not possible for Docker to determine when
services are _ready_ as this is highly specific to the requirements of a particular service/project.
If the `app` service starts before the `postgres` service is ready to accept connections on port
5432 then the `app` will crash.

One possible solution to ensure that a service is ready is to first check if it's accepting
connections on it's exposed ports, and only start any dependent services if it is. This is precisely
what the [`wait-for`](https://github.com/eficode/wait-for) script from
[eficode](https://github.com/eficode) is designed to do. The `celery_beat` and `celery_worker`
services require that both the `app` and `rabbitmq` services are ready before starting. To ensure
their availability before starting, the `celery_worker` service command first invokes `wait-for` to
check that both `rabbitmq:5672` and `app:8000` are reachable before invoking the `celery` command

```YAML
services:
  celery_worker:
    command: sh -c "wait-for rabbitmq:5672 && wait-for app:8000 && celery -A mysite worker -l info"
```

&nbsp;
### Multiple Django settings files
By default, creating a Django project using `django-admin startproject mysite` results in a single
settings file as below:

```bash
$ django-admin startproject mysite
$ tree mysite
mysite/
├── manage.py
└── mysite
    ├── __init__.py
    ├── settings.py
    ├── urls.py
    └── wsgi.py
```

In order to separate development and production specific settings, this single `settings.py` _file_
can be replaced by a `settings` _folder_ (which must contain an `__init__.py` file, thus making it a
submodule).

```bash
$ tree mysite
mysite/
├── manage.py
└── mysite
    ├── __init__.py
    ├── settings
    │   ├── development.py
    │   ├── __init__.py
    │   ├── production.py
    │   └── settings.py
    ├── urls.py
    └── wsgi.py
```

All settings common to all environments are now specified in `settings/settings.py`. This file
should still contain default values for all required settings. All that's needed for everything
to function correctly as before is a single line in the `__init__.py`

```python
# settings/__init__.py

from settings import *
```

Additional or overridden settings specific to the production environment, for example, are now
specified in the `settings/production.py` file like so

```python
# settings/production.py

import os

from settings import *

ALLOWED_HOSTS = ['app']
DEBUG = False
PRODUCTION = True
SECRET_KEY = os.environ.get('SECRET_KEY')
```

To tell Django to use a specific settings file, the `DJANGO_SETTINGS_MODULE` environment variable
must be set accordingly, i.e.,

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.production
python manage.py runserver 0:8000
```

&nbsp;
### Celery config
To ensure that the Django app does not block due to serial execution of long running tasks, celery
workers are used. Celery provides a pool of worker processes to which cpu heavy or long
running io tasks can be deferred in the form of asynchronous _tasks_. Many good guides exist which
explain how to set up Celery such as [this one](https://www.revsys.com/tidbits/celery-and-django-and-docker-oh-my/).
Whilst it can seem overwhelming at first it's actually quite straightforward once it's been set up once.

Firstly, the Celery app needs to be defined in [`mysite/celery_app.py`](./mysite/celery_app.py),
set to obtain configuration from the Django config, and to automatically discover tasks defined
throughout the Django project

```python
# mysite/celery_app.py

import os

from celery import Celery

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

app = Celery('mysite')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

Celery related configuration is pulled in from the Django settings file, specifically any variables
beginning with `'CELERY'` will be interpreted as Celery related settings.

```python
# mysite/setttings/settings.py

from celery.schedules import crontab

CELERY_BROKER_URL= 'pyamqp://rabbitmq:5672'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_BEAT_SCHEDULE = {
    'queue_every_five_mins': {
        'task': 'polls.tasks.query_every_five_mins',
        'schedule': crontab(minute=5),
    },
}
```

The message broker is specified using the `rabbitmq` service hostname which can be resolved by
any service on the `main` network. The Django app's database, i.e., the `postgres` service, will
be used as the Celery result backend. Periodic tasks to be scheduled by the `celery_beat` service
are also defined here. In this case, there is a single periodic task, `polls.tasks.query_every_five_mins`,
which will be executed every 5 minutes as specified by the crontab.

The Celery app must be added in to the Django module's `__all__` variable in `mysite/__init__.py`
like so

```python
# mysite/__init__.py

from .celery_app import app as celery_app

__all__ = ('celery_app',)
```

Finally, [tasks](http://docs.celeryproject.org/en/latest/userguide/tasks.html) to be
executed by the workers can be defined within each app of the Django project,
usually in files named `tasks.py` by convention. The [`polls/tasks.py`](./polls/tasks.py) file
contains the following (very contrived!) tasks

```python
# polls/tasks.py

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
```

Note the use of the `@task` decorator, which is required to make the associated callable
discoverable and executable by the celery workers.

Delegating a task to Celery and checking/fetching its results is straightforward as demonstrated in
these view functions from [`polls/views.py`](./polls/views.py)

```python
# polls/views.py

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
```

Finally, the Celery services need to be defined in the
[`docker-compose.yaml`](./docker-compose.yaml) file, as can be seen [here](#base-compose). Note, the
Celery services need to be on the same network as the `app`, `postgres`, and `rabbitmq` services and
are defined as being dependent on these services. The Celery services need access to the same code
as the Django app, so these services reuse the `app-image` Docker image which is built by the `app`
service.

Multiple instances of the worker process can be created using the `docker-compose scale` command.
It's also possible to set the number of workers when invoking the `up` command like so

```bash
docker-compose up --scale celery_worker=4
```

&nbsp;
### Nginx
In production, Nginx should be used as the web server for the app, passing requests to
gunicorn which in turn interacts with the app via the app's Web Server Gateway Interface (WSGI).
This great [guide](https://www.codementor.io/samueljames/nginx-setting-up-a-simple-proxy-server-using-docker-and-python-django-f7hy4e6jv)
explains setting up Nginx+gunicorn+Django in a Docker environment.

In production, the following command is executed by the `app` service to run the `gunicorn` web
server to serve requests for the Django application after first waiting for the `postgres` service
to be ready, collecting static files into the `static` volume shared with the `nginx` service, and
performing any necessary database migrations

```bash
wait-for postgres:5432\
  && python manage.py collectstatic --no-input\
  && python manage.py migrate\
  && gunicorn mysite.wsgi -b 0.0.0.0:8000
```

To successfully run the `app` service's production command, `gunicorn` must
be added to the project's requirements in `requirements/production.in`. It is the packages installed
using this requirements file which are frozen (`python -m pip freeze > requirements.txt`) in to the
top level `requirements.txt` file used by the `Dockerfile` to install the Python dependencies for
the `app-image` Docker image.

```
# requirements/prod.in

-r base.in
gunicorn
```

The `app` service exposes port 8000 on which the `gunicorn` web server is listening. The `nginx`
service needs to be configured to act as a proxy server, listening for requests on port 80 and
forwarding these on to the app on port 8000. Configuration for the `nginx` service is specified in
the [`nginx.conf`](./nginx.conf) file shown below which is bind mounted into the `nginx` service at
`/etc/nginx/nginx.conf`.

```conf
# nginx.conf

user  nginx;
worker_processes  1;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
  worker_connections  1024;  ## Default: 1024, increase if you have lots of clients
}

http {
  include       /etc/nginx/mime.types;
  default_type  application/octet-stream;
  sendfile        on;
  keepalive_timeout  5s;

  log_format  main  '$remote_addr - $remote_user [$time_local] "$request" $status '
    '$body_bytes_sent "$http_referer" "$http_user_agent" "$http_x_forwarded_for"';
  access_log  /var/log/nginx/access.log  main;

  upstream app {
    server app:8000;
  }

  server {
    listen 80;
    server_name localhost;
    charset utf-8;

    location /static/ {
      autoindex on;
      alias /var/www/app/static/;
    }

    location / {
      proxy_redirect     off;
      proxy_set_header   Host app;
      proxy_set_header   X-Real-IP $remote_addr;
      proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header   X-Forwarded-Host $server_name;
      proxy_pass http://app;
    }

    location /protected/ {
      internal;
      alias /var/www/app/static/download/;
    }

  }
}
```

The proxy is configured to serve any requests for static assets on routes beginning with
`/static/` directly. This reduces the burden of serving images and other static assets from the Django app,
which are more efficiently handled by Nginx. Any requests on routes beginning with `/protected/`
will also be handled directly by Nginx, but this internal redirection will be invisible to the
client. This allows the Django app to defer serving large files to Nginx, which is more efficient
for this task, thus preventing the app from blocking other requests whilst large files are being served.

A request for the route `/polls/download/` will be routed by Nginx to gunicorn and reach the Django
app's `download` view shown below. The Django view could then be used, for example, to check if a
user is logged in and has permission to download the requested file. The file can then be
created/selected inside the view function before the actual serving of the file is handed over to
Nginx using the `X-Accel-Redirect` header. The app returns a regular HTTP response instead of a file
response.  Nginx detects the `X-Accel-Redirect` header and takes over serving the file. In this
contrived example, the `app` service creates a file in `/static/download/` inside the shared `static` volume,
which corresponds to `/var/www/app/static/download/` in the `nginx` service's filesystem. The file
path in the `X-Accel-Redirect` is set to `/protected/` which is picked up by Nginx and converted to
`/var/www/app/static/download/` due to the alias defined in the configuration. Importantly, because
the app runs as `root` with a uid of 0, and the `nginx` service uses the `nginx` user with a
different uid, the permissions on the file must be set to "readable by others" so that the nginx
worker can successfully read and, hence, serve the file to the client. This mechanism can
easily and efficiently facilitate downloads of large, protected files/assets.

```python
# polls/views.py

import os
import stat
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.http import FileResponse, HttpResponse


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
```

&nbsp;
### Python environments
A common complaint about Python is difficulty managing environments and issues caused be the
presence of different versions of Python on a single system. To a greater or lesser extent these
issues are eliminated by the use of virtual environments using
[`virtualenv`](https://docs.python-guide.org/dev/virtualenvs/#lower-level-virtualenv). It's
considered best practice to only include dependencies in your project's environment which are
required; however, it's also often convenient to have additional packages available which help to
make the development process more smooth/efficient. To this end it is possible to create multiple
virtual environments which leverage inheritance and to split the dependencies into multiple
requirements files which can also make use of inheritance.

This project makes use of separate requirements files for each different environment:

```bash
$ tree requirements
requirements
├── base.in
├── dev.in
├── prod.in
└── test.in
```

Common requirements for all environments are specified in the `requirements/base.in` file:


```bash
$ cat requirements/base.in
Django
celery
django-celery-beat
django-celery-results
psycopg2
```

The `requirements/dev.in` and `requirements/prod.in` files inherit the common dependencies from
`requirements/base.in` and specify additional dependencies specific to the development and
production environments respectively.

```bash
$ cat requirements/dev.in
-r base.in
ipython

$ cat requirements/prod.in
-r base.in
gunicorn
```

Distinct virtual environments can be created for each requirements file which inherit from a base
virtual env using `.pth` files like so

```bash
$ virtualenv -p python3.6 venv
$ source venv/bin/activate
(venv) $ python -m pip install -r requirements/base.in
(venv) $ deactivate
$ virtualenv -p venv/bin/python venv-dev
$ realpath venv/lib/python3.6/site-packages > venv-dev/lib/python3.6/site-packages/base_venv.pth
$ source venv-dev/bin/activate
(venv-dev) $ python -m pip install -r requirements/dev.in
```

When installing the development dependencies, only those dependencies not already present in the
base environment will be installed.
