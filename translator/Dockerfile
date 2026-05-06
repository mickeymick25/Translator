FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie des modules core et modes
COPY core/ ./core/
COPY modes/ ./modes/
COPY service.py .

# Création des répertoires de travail
RUN mkdir -p /app/output /app/output/excel /app/source /app/doc

ENTRYPOINT ["python", "service.py"]
