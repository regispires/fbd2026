# syntax=docker/dockerfile:1

FROM astral/uv:python3.14-trixie-slim@sha256:da0f1f04404173d7d2fa158112e09624d5a80262efa86c89882b68389dfd44eb

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
CMD ["uv", "run", "fastapi", "run"]
