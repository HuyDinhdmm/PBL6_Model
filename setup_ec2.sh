#!/bin/bash
# Script cài đặt môi trường trên EC2 instance
# Chạy script này trên EC2 instance: bash setup_ec2.sh

set -e

echo "🔧 Bắt đầu cài đặt môi trường trên EC2..."

# Cập nhật hệ thống
echo "📦 Cập nhật hệ thống..."
sudo apt-get update
sudo apt-get upgrade -y

# Cài đặt Docker
echo "🐳 Cài đặt Docker..."
if ! command -v docker &> /dev/null; then
    sudo apt-get install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "✅ Docker đã được cài đặt"
else
    echo "✅ Docker đã có sẵn"
fi

# Cài đặt NVIDIA Container Toolkit
echo "🎮 Cài đặt NVIDIA Container Toolkit..."
if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    sudo systemctl restart docker
    echo "✅ NVIDIA Container Toolkit đã được cài đặt"
else
    echo "✅ NVIDIA Container Toolkit đã có sẵn"
fi

# Cài đặt Python và pip (nếu cần cho download_model.py)
echo "🐍 Cài đặt Python và pip..."
sudo apt-get install -y python3 python3-pip
pip3 install --user huggingface_hub

# Kiểm tra GPU
echo "🔍 Kiểm tra GPU..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
    echo "✅ GPU đã được phát hiện"
else
    echo "⚠️  nvidia-smi không tìm thấy. Đảm bảo bạn đang sử dụng GPU instance."
fi

# Kiểm tra Docker GPU support
echo "🔍 Kiểm tra Docker GPU support..."
if docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
    echo "✅ Docker có thể truy cập GPU"
else
    echo "⚠️  Docker không thể truy cập GPU. Kiểm tra lại cài đặt."
fi

echo ""
echo "✅ Cài đặt hoàn tất!"
echo ""
echo "📝 Các bước tiếp theo:"
echo "1. Upload code lên EC2 (sử dụng SCP hoặc Git)"
echo "2. Tải model: python3 download_model.py"
echo "3. Build Docker: docker build -t vintern-invoice-api:1.0 ."
echo "4. Chạy container: docker run --gpus all -d -p 8000:8000 --name vintern_server vintern-invoice-api:1.0"


