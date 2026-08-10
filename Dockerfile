FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_SOURCE=rds \
    RDS_SSL_CA=/etc/ssl/certs/aws-rds-global-bundle.pem

# Amazon's global RDS trust bundle enables MySQL server certificate and
# hostname verification in ECS. Refresh it whenever the image is rebuilt.
ADD https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/aws-rds-global-bundle.pem

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
