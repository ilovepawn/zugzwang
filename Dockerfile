FROM python:3.14-slim

WORKDIR /app

RUN pip install poetry && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-directory

COPY . .

EXPOSE 8000

COPY entrypoint.sh .
CMD ["./entrypoint.sh"]
