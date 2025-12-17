# Hướng Dẫn Deploy lên Vast.ai

## 📋 Tổng Quan

Vast.ai là nền tảng GPU cloud **rẻ nhất** hiện tại:
- **Chi phí**: $0.10 - $0.30/giờ (RTX 3090, 4090)
- **GPU**: RTX 3090, 4090, A100, etc.
- **RAM**: 24GB+ 
- **Phù hợp**: Production với chi phí thấp

## 🚀 Bước 1: Đăng Ký và Tạo Instance

### 1.1 Đăng ký tài khoản

1. Vào https://vast.ai
2. Đăng ký tài khoản (có thể dùng GitHub)
3. Nạp tiền vào account (minimum $5-10)

### 1.2 Tìm và Tạo Instance

1. Vào **"Create"** → **"Compute"**
2. Tìm instance phù hợp:
   - **GPU**: RTX 3090 hoặc RTX 4090 (rẻ nhất)
   - **RAM**: Tối thiểu 24GB
   - **Storage**: Tối thiểu 50GB
   - **OS**: Ubuntu 22.04 (khuyến nghị)

3. **Lọc tìm kiếm:**
   - GPU: RTX 3090 hoặc RTX 4090
   - Price: < $0.30/giờ
   - CUDA: 11.8+
   - Disk space: > 50GB

4. Click **"Rent"** trên instance phù hợp

### 1.3 Lấy Thông Tin SSH

Sau khi tạo instance, Vast.ai sẽ cung cấp:
- **IP Address**: `123.45.67.89`
- **SSH Port**: Thường là `22` hoặc port khác
- **SSH Command**: Copy command này

Ví dụ SSH command:
```bash
ssh -p 22222 root@123.45.67.89
```

## 🚀 Bước 2: Deploy Tự Động (Khuyến Nghị)

### 2.1 Sử dụng Script Tự Động

```bash
# Nếu có SSH key
./deploy_vastai.sh <VASTAI-IP> <SSH-PORT> <KEY-FILE>

# Ví dụ:
./deploy_vastai.sh 123.45.67.89 22222 ~/.ssh/vastai_key

# Nếu dùng password (bỏ qua KEY_FILE)
./deploy_vastai.sh 123.45.67.89 22222
```

Script sẽ tự động:
- ✅ Upload code lên Vast.ai
- ✅ Cài đặt Docker và NVIDIA Container Toolkit
- ✅ Tải model nếu chưa có
- ✅ Build và chạy Docker container

### 2.2 Kiểm Tra Deploy

```bash
# SSH vào instance
ssh -p <SSH-PORT> root@<VASTAI-IP>

# Kiểm tra container
docker ps

# Xem logs
docker logs -f vintern_server
```

## 🚀 Bước 3: Truy Cập API

### 3.1 Vấn Đề: Vast.ai Không Có Public IP

Vast.ai instances thường **không có public IP trực tiếp**. Có 2 cách:

### Cách 1: SSH Tunnel (Khuyến Nghị)

Tạo SSH tunnel từ máy local:

```bash
# Tạo tunnel
ssh -L 8000:localhost:8000 -p <SSH-PORT> root@<VASTAI-IP>

# Giữ terminal này mở, sau đó truy cập:
# http://localhost:8000
# http://localhost:8000/docs
```

### Cách 2: Ngrok (Cho Public Access)

Trên Vast.ai instance:

```bash
# Cài đặt ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Đăng ký ngrok (free): https://ngrok.com
# Lấy authtoken và chạy:
ngrok config add-authtoken <YOUR-TOKEN>

# Expose port 8000
ngrok http 8000
```

Ngrok sẽ cung cấp public URL như:
```
https://abc123.ngrok.io
```

## 🚀 Bước 4: Deploy Thủ Công (Nếu Script Không Hoạt Động)

### 4.1 SSH vào Instance

```bash
ssh -p <SSH-PORT> root@<VASTAI-IP>
```

### 4.2 Cài Đặt Docker

```bash
# Cài đặt Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Cài đặt NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Kiểm tra GPU
nvidia-smi
```

### 4.3 Upload Code

Từ máy local:

```bash
# Upload files
scp -P <SSH-PORT> app.py requirements.txt Dockerfile download_model.py root@<VASTAI-IP>:~/InternVL_API_Project/
scp -P <SSH-PORT> -r internvl_local root@<VASTAI-IP>:~/InternVL_API_Project/ 2>/dev/null || echo "Model sẽ được tải trên server"
```

### 4.4 Tải Model

Trên Vast.ai instance:

```bash
cd ~/InternVL_API_Project

# Cài đặt Python dependencies
pip3 install huggingface_hub

# Tải model
python3 download_model.py
```

### 4.5 Build và Chạy Container

```bash
cd ~/InternVL_API_Project

# Build image
docker build -f Dockerfile -t vintern-invoice-api:1.0 .

# Chạy container
docker run --gpus all -d -p 8000:8000 --name vintern_server --restart unless-stopped vintern-invoice-api:1.0

# Kiểm tra
docker logs -f vintern_server
```

## 💰 Chi Phí

### Ước Tính:

- **RTX 3090**: ~$0.20-0.30/giờ
- **RTX 4090**: ~$0.30-0.50/giờ
- **A100**: ~$1.00-2.00/giờ

### Chi Phí Tháng (24/7):

- **RTX 3090**: ~$144-216/tháng
- **RTX 4090**: ~$216-360/tháng

### Tiết Kiệm:

- Chỉ trả tiền khi instance đang chạy
- Có thể stop instance khi không dùng
- Rẻ hơn AWS EC2 50-70%

## ⚠️ Lưu Ý Quan Trọng

### 1. Instance Có Thể Bị Terminate

- Owner có thể terminate instance nếu họ cần GPU
- **Giải pháp**: Chọn instance có rating cao, uptime tốt

### 2. Không Có Public IP

- Vast.ai instances không có public IP trực tiếp
- **Giải pháp**: Dùng SSH tunnel hoặc ngrok

### 3. Data Persistence

- Data sẽ mất nếu instance bị terminate
- **Giải pháp**: 
  - Backup model lên S3/Google Drive
  - Mount external storage
  - Sử dụng Vast.ai storage (có phí)

### 4. Network Speed

- Upload/download có thể chậm
- **Giải pháp**: Tải model trước khi deploy

## 🔧 Troubleshooting

### Container Không Start

```bash
# Kiểm tra logs
docker logs vintern_server

# Kiểm tra GPU
nvidia-smi

# Kiểm tra Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### Model Không Tải Được

```bash
# Kiểm tra disk space
df -h

# Kiểm tra network
ping huggingface.co

# Tải thủ công
cd ~/InternVL_API_Project
python3 download_model.py
```

### API Không Truy Cập Được

```bash
# Kiểm tra container đang chạy
docker ps

# Kiểm tra port
netstat -tulpn | grep 8000

# Test local
curl http://localhost:8000/health
```

## 📊 So Sánh với AWS

| Tính Năng | Vast.ai | AWS EC2 |
|-----------|---------|---------|
| **Chi phí** | $0.20/giờ | $0.50-0.75/giờ |
| **GPU** | RTX 3090/4090 | T4 |
| **Setup** | Trung bình | Dễ |
| **Uptime** | Phụ thuộc owner | 99.99% |
| **Support** | Community | Official |
| **Public IP** | Không | Có |

## 🎯 Kết Luận

**Vast.ai phù hợp khi:**
- ✅ Cần GPU mạnh với chi phí thấp
- ✅ Chấp nhận risk instance có thể bị terminate
- ✅ Có thể setup SSH tunnel hoặc ngrok
- ✅ Không cần 99.99% uptime

**Không phù hợp khi:**
- ❌ Cần uptime 100%
- ❌ Cần public IP trực tiếp
- ❌ Không muốn setup thủ công

---

## 📞 Hỗ Trợ

- Vast.ai Docs: https://vast.ai/docs
- Vast.ai Discord: https://discord.gg/vast
- GitHub Issues: [Your repo]
