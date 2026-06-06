FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port 7860 which is Hugging Face's default port
EXPOSE 7860

# Command to run Taipy, binding it to all hosts and HF's port
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "7860"]