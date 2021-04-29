FROM python:3.9-alpine3.13

# Install dependencies required for psycopg2 python package
RUN apk update && apk add libpq
RUN apk update && apk add --virtual .build-deps gcc python3-dev musl-dev postgresql-dev

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY . .
RUN mv wait-for /bin/wait-for

RUN pip install --no-cache-dir -r requirements.txt

# Remove dependencies only required for psycopg2 build
RUN apk del .build-deps

EXPOSE 8000

CMD ["gunicorn", "mysite.wsgi", "0:8000"]
