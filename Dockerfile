# Sử dụng Base Image có sẵn PyTorch và CUDA Runtime
# nvcr.io/nvidia/pytorch:24.03-py3 sử dụng Python 3.10
FROM nvcr.io/nvidia/pytorch:24.03-py3

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép các tệp cài đặt và mã nguồn
COPY requirements.txt .
COPY app.py .

# Sao chép mô hình đã tải về cục bộ vào Container
# Đảm bảo thư mục internvl_local chứa model nằm ở thư mục gốc của dự án
COPY internvl_local/ /app/internvl_local/

# Cài đặt các thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Mở cổng 8000
EXPOSE 8000

# Lệnh khởi chạy server bằng Uvicorn
# --host 0.0.0.0 là bắt buộc để truy cập từ bên ngoài Container
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
