# syntax=docker/dockerfile:1

FROM astral/uv:python3.14-alpine@sha256:4ce2a2ef69130ffb97688c8446ae771415035406355fbcb7932c59a535f82888

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

COPY ./uv.lock ./pyproject.toml .

RUN uv sync --locked --no-dev

COPY . .

# Expose the port that the application listens on.
EXPOSE 8000

# Run the application on the production server.
CMD ["uv", "run", "-m", "app.main"]
