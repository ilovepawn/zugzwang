FROM python:3.13-slim

WORKDIR /app

RUN pip install poetry==2.3.4 && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-directory

COPY . .

RUN useradd --create-home --shell /bin/bash app && chmod +x ./entrypoint.sh
USER app

EXPOSE 8000

CMD ["./entrypoint.sh"]
