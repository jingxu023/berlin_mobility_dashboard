# Berlin Mobility Dashboard
# Streamlit production image

FROM python:3.12-slim

# Prevent Python from writing .pyc files
# and force logs to appear immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Streamlit should run from a non-root working directory
WORKDIR /app


# System dependencies

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*



# Python dependencies

# Copy requirements first so Docker can cache this layer
COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt


# Application files

COPY . .


# Security: run as non-root user

RUN useradd --create-home --shell /bin/bash streamlit && \
    chown -R streamlit:streamlit /app

USER streamlit



# Streamlit
EXPOSE 8502

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]