FROM python:3.11-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/api

CMD ["fastapi", "run", "api/main.py", "--host", "0.0.0.0", "--port", "8000"]