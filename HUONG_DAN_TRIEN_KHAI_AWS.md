# Hướng Dẫn Triển Khai InternVL/FastAPI lên AWS

## Tổng Quan

Ứng dụng này cần GPU để chạy model InternVL, vì vậy có các phương án triển khai sau trên AWS:

## Phương Án 1: EC2 với GPU Instance (Khuyến Nghị)

### Bước 1: Tạo EC2 Instance với GPU

1. **Đăng nhập AWS Console** → EC2 → Launch Instance

2. **Chọn AMI (Amazon Machine Image):**
   - **Deep Learning AMI (Ubuntu)** - Đã có sẵn CUDA, cuDNN, PyTorch
   - Hoặc **Ubuntu 22.04 LTS** và cài đặt Docker sau

3. **Chọn Instance Type với GPU:**
   - **g4dn.xlarge** (1 GPU, 4 vCPU, 16GB RAM) - Phù hợp cho model nhỏ
   - **g4dn.2xlarge** (1 GPU, 8 vCPU, 32GB RAM) - Khuyến nghị
   - **g5.xlarge** (1 GPU, 4 vCPU, 16GB RAM) - GPU mới hơn
   - **p3.2xlarge** (1 GPU, 8 vCPU, 61GB RAM) - Mạnh hơn, đắt hơn

4. **Cấu hình Security Group:**
   - Mở port **8000** (HTTP) từ IP của bạn hoặc 0.0.0.0/0 (nếu cần truy cập công khai)
   - Mở port **22** (SSH) để kết nối

5. **Tạo Key Pair** để SSH vào instance

### Bước 2: Kết Nối và Cài Đặt

```bash
# SSH vào EC2 instance
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>

# Cập nhật hệ thống
sudo apt-get update
sudo apt-get upgrade -y

# Cài đặt Docker
sudo apt-get install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# Cài đặt NVIDIA Container Toolkit (cho GPU support)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Kiểm tra GPU
nvidia-smi
```

### Bước 3: Upload Code và Model lên EC2

**Cách 1: Sử dụng SCP để upload files**

```bash
# Từ máy local của bạn
scp -i your-key.pem -r . ubuntu@<EC2-PUBLIC-IP>:~/InternVL_API_Project/

# Hoặc chỉ upload các file cần thiết
scp -i your-key.pem app.py requirements.txt Dockerfile ubuntu@<EC2-PUBLIC-IP>:~/InternVL_API_Project/
scp -i your-key.pem -r internvl_local ubuntu@<EC2-PUBLIC-IP>:~/InternVL_API_Project/
```

**Cách 2: Sử dụng Git (Khuyến nghị)**

```bash
# Trên EC2
cd ~
git clone <your-repo-url> InternVL_API_Project
cd InternVL_API_Project

# Tải model (nếu chưa có trong repo)
python download_model.py
```

**Cách 3: Sử dụng AWS S3**

```bash
# Upload lên S3 từ local
aws s3 cp --recursive . s3://your-bucket-name/InternVL_API_Project/

# Download từ S3 trên EC2
aws s3 cp --recursive s3://your-bucket-name/InternVL_API_Project/ ~/InternVL_API_Project/
```

### Bước 4: Build và Chạy Docker Container

```bash
cd ~/InternVL_API_Project

# Build Docker image
docker build -t vintern-invoice-api:1.0 .

# Chạy container với GPU
docker run --gpus all -d -p 8000:8000 --name vintern_server --restart unless-stopped vintern-invoice-api:1.0

# Xem logs
docker logs -f vintern_server
```

### Bước 5: Kiểm Tra

```bash
# Kiểm tra container đang chạy
docker ps

# Test API từ EC2
curl http://localhost:8000/docs

# Hoặc từ máy local của bạn
curl http://<EC2-PUBLIC-IP>:8000/docs
```

---

## Phương Án 2: AWS ECS với GPU Support

### Yêu cầu:
- ECS Cluster với EC2 instances có GPU
- Task Definition với GPU resource

### Bước 1: Tạo ECR Repository

```bash
# Tạo repository trên ECR
aws ecr create-repository --repository-name vintern-invoice-api

# Login vào ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build và push image
docker build -t vintern-invoice-api:1.0 .
docker tag vintern-invoice-api:1.0 <account-id>.dkr.ecr.us-east-1.amazonaws.com/vintern-invoice-api:1.0
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/vintern-invoice-api:1.0
```

### Bước 2: Tạo Task Definition

Tạo file `task-definition.json`:

```json
{
  "family": "vintern-invoice-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["EC2"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "vintern-api",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/vintern-invoice-api:1.0",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "resourceRequirements": [
        {
          "type": "GPU",
          "value": "1"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/vintern-invoice-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Bước 3: Đăng ký Task Definition và Chạy Service

```bash
# Đăng ký task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Tạo service
aws ecs create-service \
  --cluster your-cluster-name \
  --service-name vintern-api-service \
  --task-definition vintern-invoice-api \
  --desired-count 1 \
  --launch-type EC2
```

---

## Phương Án 3: AWS SageMaker

SageMaker phù hợp hơn cho training, nhưng có thể dùng để deploy inference endpoint.

### Tạo SageMaker Endpoint với Custom Container

1. Tạo SageMaker Model
2. Deploy Endpoint với GPU instance
3. Sử dụng boto3 để gọi API

---

## Chi Phí Ước Tính

### EC2 g4dn.2xlarge:
- **On-Demand**: ~$0.75/giờ (~$540/tháng nếu chạy 24/7)
- **Spot Instance**: ~$0.23/giờ (có thể bị terminate)

### EC2 g4dn.xlarge:
- **On-Demand**: ~$0.526/giờ (~$379/tháng)
- **Spot Instance**: ~$0.16/giờ

### Lưu Ý:
- Chỉ chạy khi cần để tiết kiệm chi phí
- Sử dụng Spot Instances cho dev/test
- Tắt instance khi không dùng

---

## Bảo Mật

1. **Security Group**: Chỉ mở port cần thiết
2. **IAM Roles**: Sử dụng IAM roles thay vì access keys
3. **HTTPS**: Cân nhắc dùng Application Load Balancer với SSL certificate
4. **VPC**: Đặt instance trong private subnet nếu có thể

---

## Monitoring và Logging

### CloudWatch Logs

```bash
# Xem logs từ Docker container
docker logs vintern_server

# Hoặc cấu hình CloudWatch Logs driver trong Docker
```

### CloudWatch Metrics
- Monitor CPU, Memory, GPU utilization
- Set up alarms cho downtime

---

## Auto Scaling (Nếu cần)

1. Tạo Application Load Balancer
2. Tạo Target Group
3. Cấu hình Auto Scaling Group với GPU instances
4. Set up scaling policies dựa trên CPU/Request count

---

## Khuyến Nghị

**Cho Production:**
- Sử dụng **EC2 g4dn.2xlarge** với Auto Scaling
- Đặt sau Application Load Balancer
- Sử dụng Route 53 cho domain
- Enable CloudWatch monitoring

**Cho Development/Testing:**
- Sử dụng **EC2 g4dn.xlarge Spot Instance**
- Tắt instance khi không dùng
- Sử dụng AWS Systems Manager Session Manager thay vì SSH

---

## Troubleshooting

### GPU không được nhận diện:
```bash
# Kiểm tra NVIDIA driver
nvidia-smi

# Kiểm tra Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### Container không start:
```bash
# Xem logs
docker logs vintern_server

# Kiểm tra model path
docker exec -it vintern_server ls -la /app/internvl_local/
```

### Port không accessible:
- Kiểm tra Security Group rules
- Kiểm tra EC2 instance firewall
- Kiểm tra container đang chạy: `docker ps`


