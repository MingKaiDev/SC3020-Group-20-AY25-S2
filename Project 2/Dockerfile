FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY utils/ ./utils/
COPY data/ ./data/

# Run the setup script
CMD ["python", "utils/setup_tpch.py"]
