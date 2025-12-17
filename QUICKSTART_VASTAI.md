# 🚀 Quick Start: Deploy lên Vast.ai

## Bước 1: Tạo Instance trên Vast.ai

1. Đăng ký: https://vast.ai
2. Nạp tiền: Minimum $5-10
3. Tạo instance:
   - Vào **"Create"** → **"Compute"**
   - Tìm: RTX 3090 hoặc RTX 4090
   - Giá: < $0.30/giờ
   - RAM: > 24GB
   - Disk: > 50GB
   - OS: Ubuntu 22.04
4. Click **"Rent"**

## Bước 2: Lấy SSH Info

Sau khi tạo, Vast.ai cung cấp:
- **IP**: `123.45.67.89`
- **Port**: `22222` (hoặc port khác)
- **SSH Command**: Copy command này

## Bước 3: Deploy

```bash
# Cho script quyền thực thi
chmod +x deploy_vastai.sh

# Chạy deploy (nếu có SSH key)
./deploy_vastai.sh <IP> <PORT> <KEY-FILE>

# Hoặc dùng password (bỏ qua KEY-FILE)
./deploy_vastai.sh <IP> <PORT>
```

Ví dụ:
```bash
./deploy_vastai.sh 123.45.67.89 22222
```

## Bước 4: Truy Cập API

Vast.ai không có public IP, dùng SSH tunnel:

```bash
# Tạo tunnel (giữ terminal này mở)
ssh -L 8000:localhost:8000 -p <PORT> root@<IP>

# Sau đó truy cập:
# http://localhost:8000
# http://localhost:8000/docs
```

## Hoặc Dùng Ngrok (Public Access)

```bash
# SSH vào instance
ssh -p <PORT> root@<IP>

# Cài ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Đăng ký tại https://ngrok.com (free)
# Lấy token và chạy:
ngrok config add-authtoken <TOKEN>
ngrok http 8000
```

## ✅ Xong!

API sẽ chạy trên Vast.ai với GPU RTX 3090/4090.

**Chi phí**: ~$0.20-0.30/giờ = ~$144-216/tháng (24/7)

---

Xem chi tiết trong `HUONG_DAN_VASTAI.md`

