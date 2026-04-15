FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[web,pdf,xlsx]"
EXPOSE 8000
ENV FINXCLOUD_ADMIN_USER=admin
ENV FINXCLOUD_ADMIN_PASS=changeme
CMD ["uvicorn", "finxcloud.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
