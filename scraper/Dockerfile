# Use official Python 3.11 image
FROM python:3.11-slim

# Install system dependencies for Selenium/Pyppeteer
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg ca-certificates fonts-liberation \
    libnss3 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxi6 libxtst6 libpangocairo-1.0-0 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libxrandr2 libxss1 libasound2 libglib2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project
COPY . .

# Run the crawler by default
CMD ["python", "crawler.py"]
