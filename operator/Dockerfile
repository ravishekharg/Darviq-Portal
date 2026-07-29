FROM python:3.12-slim

WORKDIR /app

RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --no-create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup operator.py .

USER appuser

CMD ["kopf", "run", "--standalone", "operator.py"]
