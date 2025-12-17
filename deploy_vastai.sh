#!/bin/bash
# Script tự động triển khai lên Vast.ai
# Sử dụng: ./deploy_vastai.sh <VASTAI-IP> <SSH-PORT> <KEY-FILE>
# 
# Lưu ý: Vast.ai thường dùng SSH key hoặc password
# Nếu dùng password, bạn sẽ cần nhập thủ công

set -e

VASTAI_IP=$1
SSH_PORT=${2:-22}  # Mặc định port 22, nhưng Vast.ai có thể dùng port khác
KEY_FILE=$3
PROJECT_DIR="InternVL_API_Project"

if [ -z "$VASTAI_IP" ]; then
    echo "Usage: ./deploy_vastai.sh <VASTAI-IP> [SSH-PORT] [KEY-FILE]"
    echo ""
    echo "Ví dụ:"
    echo "  ./deploy_vastai.sh 123.45.67.89 22 ~/.ssh/vastai_key"
    echo "  ./deploy_vastai.sh 123.45.67.89 22222  # Nếu dùng password, bỏ qua KEY_FILE"
    echo ""
    echo "Lưu ý:"
    echo "  - Vast.ai thường cung cấp SSH command trong dashboard"
    echo "  - Copy SSH command từ Vast.ai và thay thế IP/port"
    echo "  - Nếu dùng password, script sẽ hỏi password khi cần"
    exit 1
fi

echo "🚀 Bắt đầu triển khai lên Vast.ai: $VASTAI_IP:$SSH_PORT"

# Xác định SSH command
if [ -n "$KEY_FILE" ] && [ -f "$KEY_FILE" ]; then
    SSH_CMD="ssh -i $KEY_FILE -p $SSH_PORT"
    SCP_CMD="scp -i $KEY_FILE -P $SSH_PORT"
    echo "✅ Sử dụng SSH key: $KEY_FILE"
else
    SSH_CMD="ssh -p $SSH_PORT"
    SCP_CMD="scp -P $SSH_PORT"
    echo "⚠️  Không có SSH key, sẽ dùng password authentication"
    echo "   Bạn sẽ cần nhập password khi được hỏi"
fi

# Xác định user (Vast.ai thường dùng 'root' hoặc 'vast')
# Thử 'root' trước, nếu không được sẽ thử 'vast'
VASTAI_USER="root"

# Tạo thư mục trên Vast.ai
echo "📁 Tạo thư mục dự án trên Vast.ai..."
$SSH_CMD $VASTAI_USER@"$VASTAI_IP" "mkdir -p ~/$PROJECT_DIR" || {
    echo "⚠️  Thử với user 'vast'..."
    VASTAI_USER="vast"
    $SSH_CMD $VASTAI_USER@"$VASTAI_IP" "mkdir -p ~/$PROJECT_DIR"
}

# Upload files
echo "📤 Upload files..."
$SCP_CMD app.py requirements.txt Dockerfile Dockerfile.cpu download_model.py $VASTAI_USER@"$VASTAI_IP":~/$PROJECT_DIR/
$SCP_CMD -r internvl_local $VASTAI_USER@"$VASTAI_IP":~/$PROJECT_DIR/ 2>/dev/null || echo "⚠️  Thư mục internvl_local không tồn tại, sẽ tự động tải model trên Vast.ai"

# Chạy script setup trên Vast.ai
echo "⚙️  Cài đặt Docker và kiểm tra GPU..."
$SSH_CMD $VASTAI_USER@"$VASTAI_IP" << 'ENDSSH'
    cd ~/$PROJECT_DIR
    
    # Cài đặt Docker (nếu chưa có)
    if ! command -v docker &> /dev/null; then
        echo "📦 Cài đặt Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        echo "✅ Docker đã được cài đặt"
    else
        echo "✅ Docker đã có sẵn"
    fi

    # Kiểm tra GPU
    echo "🔍 Kiểm tra GPU..."
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        echo "✅ GPU được phát hiện!"
        nvidia-smi
        HAS_GPU=true
        
        # Cài đặt NVIDIA Container Toolkit nếu chưa có
        echo "📦 Cài đặt NVIDIA Container Toolkit..."
        if ! docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi &> /dev/null; then
            distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
            curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - 2>/dev/null || true
            curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
            sudo apt-get update
            sudo apt-get install -y nvidia-container-toolkit
            sudo systemctl restart docker
            echo "✅ NVIDIA Container Toolkit đã được cài đặt"
        else
            echo "✅ NVIDIA Container Toolkit đã có sẵn"
        fi
    else
        echo "⚠️  GPU không được phát hiện - sẽ chạy trên CPU"
        HAS_GPU=false
    fi
ENDSSH

# Tải model nếu chưa có
echo "🤖 Kiểm tra và tải model nếu cần..."
$SSH_CMD $VASTAI_USER@"$VASTAI_IP" << 'ENDSSH'
    cd ~/$PROJECT_DIR
    
    # Cài đặt Python và pip nếu chưa có
    if ! command -v python3 &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip
    fi
    
    # Kiểm tra model đã tồn tại chưa
    if [ ! -d "internvl_local" ] || [ ! -f "internvl_local/model.safetensors" ]; then
        echo "📥 Model chưa có, bắt đầu tải từ Hugging Face Hub..."
        echo "⏳ Quá trình này có thể mất 10-15 phút..."
        
        # Cài đặt huggingface_hub nếu chưa có
        pip3 install --user huggingface_hub 2>/dev/null || python3 -m pip install --user huggingface_hub
        
        # Tải model
        python3 download_model.py
    else
        echo "✅ Model đã tồn tại, bỏ qua việc tải lại."
    fi
ENDSSH

# Build và chạy Docker container
echo "🐳 Build và chạy Docker container..."
$SSH_CMD $VASTAI_USER@"$VASTAI_IP" << 'ENDSSH'
    cd ~/$PROJECT_DIR

    # Dừng container cũ nếu có
    docker stop vintern_server 2>/dev/null || true
    docker rm vintern_server 2>/dev/null || true

    # Kiểm tra GPU và build image phù hợp
    echo "🔨 Building Docker image..."
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        echo "✅ Build image với CUDA support..."
        docker build -f Dockerfile -t vintern-invoice-api:1.0 .
    else
        echo "⚠️  Build image cho CPU (không có GPU)..."
        docker build -f Dockerfile.cpu -t vintern-invoice-api:1.0 .
    fi

    # Kiểm tra GPU và chạy container phù hợp
    echo "▶️  Starting container..."
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        echo "✅ Chạy container với GPU support..."
        docker run --gpus all -d -p 8000:8000 --name vintern_server --restart unless-stopped vintern-invoice-api:1.0
    else
        echo "⚠️  Chạy container trên CPU (không có GPU)..."
        docker run -d -p 8000:8000 --name vintern_server --restart unless-stopped vintern-invoice-api:1.0
    fi

    # Đợi container khởi động
    sleep 10

    # Kiểm tra logs
    echo "📋 Container logs:"
    docker logs vintern_server --tail 50
    
    # Kiểm tra container status
    echo ""
    echo "📊 Container status:"
    docker ps -a | grep vintern_server || echo "⚠️  Container không chạy!"
    
    # Hiển thị thông tin kết nối
    echo ""
    echo "🌐 Thông tin kết nối:"
    echo "   API: http://$HOSTNAME:8000"
    echo "   Swagger: http://$HOSTNAME:8000/docs"
ENDSSH

echo ""
echo "✅ Triển khai hoàn tất!"
echo ""
echo "📝 Lưu ý quan trọng:"
echo "   1. Vast.ai thường không có public IP trực tiếp"
echo "   2. Bạn cần tạo SSH tunnel để truy cập API:"
echo "      ssh -L 8000:localhost:8000 -p $SSH_PORT $VASTAI_USER@$VASTAI_IP"
echo ""
echo "   3. Sau khi tạo tunnel, truy cập:"
echo "      http://localhost:8000"
echo "      http://localhost:8000/docs"
echo ""
echo "   4. Hoặc sử dụng ngrok để expose public:"
echo "      ssh -p $SSH_PORT $VASTAI_USER@$VASTAI_IP 'ngrok http 8000'"
echo ""
echo "Để xem logs: $SSH_CMD $VASTAI_USER@$VASTAI_IP 'docker logs -f vintern_server'"
