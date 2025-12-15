# InternVL FastAPI Invoice Extraction API

API server sử dụng InternVL model để trích xuất thông tin từ hóa đơn/biên lai.

## Cấu trúc dự án

```
PBL6/
├── app.py                 # FastAPI server chính
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── download_model.py     # Script tải model từ Hugging Face
├── internvl_local/       # Thư mục chứa model (không commit lên git)
├── deploy_aws.sh         # Script tự động deploy lên AWS EC2
├── setup_ec2.sh          # Script cài đặt môi trường trên EC2
└── HUONG_DAN_TRIEN_KHAI_AWS.md  # Hướng dẫn chi tiết triển khai AWS
```

## Model

Model sử dụng: **5CD-AI/Vintern-1B-v3_5** từ Hugging Face Hub

**Lưu ý quan trọng:** Thư mục `internvl_local/` chứa model đã được thêm vào `.gitignore` vì kích thước lớn. Khi deploy lên server mới, bạn cần chạy script `download_model.py` để tải model.

## Cài đặt Local

### 1. Clone repository

```bash
git clone <your-repo-url>
cd PBL6
```

### 2. Tải model

```bash
# Cài đặt huggingface_hub
pip install huggingface_hub

# Tải model
python download_model.py
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Chạy server (local - không dùng Docker)

```bash
# Cần có GPU và CUDA
python app.py
```

Hoặc:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Sử dụng Docker (Local)

### 1. Build Docker image

```bash
docker build -t vintern-invoice-api:1.0 .
```

### 2. Chạy container với GPU

```bash
docker run --gpus all -p 8000:8000 vintern-invoice-api:1.0
```

## Triển khai lên AWS EC2

### Cách 1: Sử dụng script tự động (Khuyến nghị)

```bash
# Từ máy local của bạn
bash deploy_aws.sh <EC2-IP> <path-to-key.pem>

# Ví dụ:
bash deploy_aws.sh 54.123.45.67 ~/.ssh/my-key.pem
```

Script này sẽ tự động:
- Upload code lên EC2
- Cài đặt Docker và NVIDIA Container Toolkit
- **Tự động tải model nếu chưa có**
- Build và chạy Docker container

### Cách 2: Triển khai thủ công

Xem chi tiết trong file `HUONG_DAN_TRIEN_KHAI_AWS.md`

## API Endpoints

### POST /extract_invoice

Trích xuất thông tin từ hóa đơn/biên lai.

**Request:**
```json
{
  "image_url": "https://example.com/invoice.jpg",
  "question": "<image>\nTrích xuất tất cả các trường thông tin...",
  "max_tokens": 1024,
  "temperature": 0.0
}
```

**Response:**
```json
{
  "status": "success",
  "extraction_result": "{...JSON extracted data...}"
}
```

### Swagger UI

Truy cập: `http://localhost:8000/docs` hoặc `http://<EC2-IP>:8000/docs`

## Lưu ý về Model

- Model không được commit lên git (đã thêm vào `.gitignore`)
- Khi deploy lên server mới, script `deploy_aws.sh` sẽ tự động tải model
- Nếu tải thủ công, chạy: `python3 download_model.py` trên server
- Model sẽ được kiểm tra tự động, nếu đã tồn tại sẽ bỏ qua việc tải lại

## Yêu cầu hệ thống

- **GPU**: Cần GPU với CUDA support (NVIDIA)
- **RAM**: Tối thiểu 16GB (khuyến nghị 32GB)
- **Docker**: Với NVIDIA Container Toolkit
- **Python**: 3.8+

## Troubleshooting

### Model chưa được tải

```bash
# Kiểm tra model
ls -la internvl_local/

# Tải model nếu chưa có
python download_model.py
```

### GPU không được nhận diện

```bash
# Kiểm tra GPU
nvidia-smi

# Kiểm tra Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### Container không start

```bash
# Xem logs
docker logs vintern_server

# Kiểm tra model trong container
docker exec -it vintern_server ls -la /app/internvl_local/
```

## License

[Thêm license của bạn]


