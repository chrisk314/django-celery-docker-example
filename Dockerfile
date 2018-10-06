FROM python:3-alpine

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# Install dependencies required for psycopg2 python package
RUN apk update && apk add libpq
RUN apk update && apk add --virtual .build-deps gcc python3-dev musl-dev postgresql-dev 
COPY requirements.txt /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt
# Remove dependencies only required for psycopg2 build
RUN apk del .build-deps

COPY . /usr/src/app/
WORKDIR /usr/src/app/

EXPOSE 8000

CMD ["python", "manage.py", "runserver"]
