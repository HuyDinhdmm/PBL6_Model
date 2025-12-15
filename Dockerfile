# Dockerfile cho InternVL API trên AWS EC2
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Set working directory
WORKDIR /app

# Cài đặt Python và các dependencies hệ thống
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài đặt Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy code
COPY app.py .
COPY download_model.py .

# Tạo thư mục cho model (sẽ được mount hoặc tải vào)
RUN mkdir -p /app/internvl_local

# Expose port
EXPOSE 8000

# Chạy app
CMD ["python3", "app.py"]
