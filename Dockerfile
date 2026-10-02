# syntax=docker/dockerfile:1

FROM python:3.13.11-alpine3.23

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

RUN pip install uv==0.12.17

COPY ./uv.lock ./pyproject.toml .

RUN uv sync --locked --no-dev

COPY . .

# Expose the port that the application listens on.
EXPOSE 8000

# Run the application on the production server.
CMD ["uv", "run", "app/main.py"]
