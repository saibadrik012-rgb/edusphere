FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create a dedicated directory for our persistent database file
RUN mkdir -p /data

EXPOSE 7860

CMD ["python", "app.py"]