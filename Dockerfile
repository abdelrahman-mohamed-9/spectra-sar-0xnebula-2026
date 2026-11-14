FROM python:3.12-slim
WORKDIR /app
COPY backend backend
COPY requirements.txt requirements-dev.txt constraints-tested.txt ./
RUN python -m pip install --no-cache-dir -r requirements-dev.txt -c constraints-tested.txt \
    && groupadd --system spectra && useradd --system --gid spectra spectra \
    && install -d -m 0700 -o spectra -g spectra /state
COPY phase1 phase1
COPY phase2 phase2
COPY phase1_compat phase1_compat
COPY members members
COPY config config
COPY data data
COPY catalog.json .
ENV PYTHONPATH=/app:/app/backend/src:/app/phase1_compat/m2 \
    PYTHONDONTWRITEBYTECODE=1 \
    SPECTRA_PHASE2_STATE=/state \
    OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
USER spectra
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "phase2.application:create_local_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
