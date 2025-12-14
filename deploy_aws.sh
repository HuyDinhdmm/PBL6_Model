#!/bin/bash
# Script tự động triển khai lên AWS EC2
# Sử dụng: ./deploy_aws.sh <EC2-IP> <KEY-FILE>

set -e

EC2_IP=$1
KEY_FILE=$2
PROJECT_DIR="InternVL_API_Project"

if [ -z "$EC2_IP" ] || [ -z "$KEY_FILE" ]; then
    echo "Usage: ./deploy_aws.sh <EC2-IP> <KEY-FILE>"
    echo "Example: ./deploy_aws.sh 54.123.45.67 ~/.ssh/my-key.pem"
    exit 1
fi

echo "🚀 Bắt đầu triển khai lên AWS EC2: $EC2_IP"

# Tạo thư mục trên EC2
echo "📁 Tạo thư mục dự án trên EC2..."
ssh -i "$KEY_FILE" ubuntu@"$EC2_IP" "mkdir -p ~/$PROJECT_DIR"

# Upload files
echo "📤 Upload files..."
scp -i "$KEY_FILE" app.py requirements.txt Dockerfile ubuntu@"$EC2_IP":~/$PROJECT_DIR/
scp -i "$KEY_FILE" -r internvl_local ubuntu@"$EC2_IP":~/$PROJECT_DIR/ || echo "⚠️  Thư mục internvl_local không tồn tại, sẽ cần tải model trên EC2"

# Chạy script setup trên EC2
echo "⚙️  Cài đặt Docker và NVIDIA Container Toolkit..."
ssh -i "$KEY_FILE" ubuntu@"$EC2_IP" << 'ENDSSH'
    # Cài đặt Docker (nếu chưa có)
    if ! command -v docker &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y docker.io
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker ubuntu
    fi

    # Cài đặt NVIDIA Container Toolkit (nếu chưa có)
    if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
        curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
        sudo apt-get update
        sudo apt-get install -y nvidia-container-toolkit
        sudo systemctl restart docker
    fi

    # Kiểm tra GPU
    echo "🔍 Kiểm tra GPU..."
    nvidia-smi || echo "⚠️  GPU không được phát hiện!"
ENDSSH

# Build và chạy Docker container
echo "🐳 Build và chạy Docker container..."
ssh -i "$KEY_FILE" ubuntu@"$EC2_IP" << ENDSSH
    cd ~/$PROJECT_DIR

    # Dừng container cũ nếu có
    docker stop vintern_server 2>/dev/null || true
    docker rm vintern_server 2>/dev/null || true

    # Build image
    echo "🔨 Building Docker image..."
    docker build -t vintern-invoice-api:1.0 .

    # Chạy container
    echo "▶️  Starting container..."
    docker run --gpus all -d -p 8000:8000 --name vintern_server --restart unless-stopped vintern-invoice-api:1.0

    # Đợi container khởi động
    sleep 10

    # Kiểm tra logs
    echo "📋 Container logs:"
    docker logs vintern_server --tail 50
ENDSSH

echo ""
echo "✅ Triển khai hoàn tất!"
echo "🌐 API có thể truy cập tại: http://$EC2_IP:8000"
echo "📚 Swagger UI: http://$EC2_IP:8000/docs"
echo ""
echo "Để xem logs: ssh -i $KEY_FILE ubuntu@$EC2_IP 'docker logs -f vintern_server'"
