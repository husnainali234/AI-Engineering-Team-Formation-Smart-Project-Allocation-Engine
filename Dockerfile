FROM python:3.11-slim

WORKDIR /code

# Set environment variables to optimize Python & Pip behavior inside Docker
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=1000

# Install PyTorch CPU first in its own layer to leverage Docker caching
RUN pip install --default-timeout=1000 --retries 10 torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install the rest of your backend dependencies
COPY requirements.txt .
RUN pip install --default-timeout=1000 --retries 10 -r requirements.txt

# Copy configuration and application files
COPY alembic.ini .
COPY ./alembic ./alembic
COPY ./scripts ./scripts
COPY ./app ./app

EXPOSE 8000

# Removed --reload to prevent container restart loops on small file changes
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]