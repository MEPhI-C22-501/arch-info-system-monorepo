FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/planning-system
COPY planning-system/server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --uid 10001 --create-home planning
COPY planning-system/server ./server
COPY planning-system/docs/contracts ./docs/contracts
COPY planning-system/ui/app ./ui/app
COPY planning-system/migrations ./migrations
RUN mkdir -p /data/files && chown -R planning:planning /data
USER planning
EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
