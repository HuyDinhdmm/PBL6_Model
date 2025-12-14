import os
import io
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import requests

# --- CÁC HÀM TIỀN XỬ LÝ ẢNH ---
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

def build_transform(input_size):
    """Xây dựng pipeline chuyển đổi ảnh."""
    transform = T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])
    return transform

def find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    """Tìm tỷ lệ khung hình gần nhất với ảnh gốc."""
    best_ratio_diff = float('inf')
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio

def dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
    """Tiền xử lý ảnh động, chia ảnh thành các patches."""
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    # Tính toán các tỷ lệ khung hình mục tiêu
    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
        i * j <= max_num and i * j >= min_num)
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    # Tìm tỷ lệ khung hình gần nhất
    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size)

    # Tính toán kích thước mục tiêu
    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    # Resize ảnh
    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size
        )
        # Chia ảnh thành các phần
        split_img = resized_img.crop(box)
        processed_images.append(split_img)
    assert len(processed_images) == blocks
    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images

def load_image(image_data, input_size=448, max_num=6):
    """Tải và tiền xử lý ảnh từ bytes data."""
    # Chuyển đổi bytes thành PIL Image
    if isinstance(image_data, bytes):
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
    else:
        image = Image.open(image_data).convert('RGB')
    
    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(img) for img in images]
    pixel_values = torch.stack(pixel_values)
    return pixel_values

# --- CẤU HÌNH GLOBAL ---
# ĐƯỜNG DẪN CỤC BỘ BÊN TRONG CONTAINER
LOCAL_MODEL_PATH = "/app/internvl_local/" 
MODEL_NAME = "5CD-AI/Vintern-1B-v3_5" 

# Khởi tạo đối tượng model và tokenizer rỗng
model = None
tokenizer = None
app = FastAPI()

# Định nghĩa Schema cho Request
class InferenceRequest(BaseModel):
    image_url: str 
    question: str = """<image>
Trích xuất tất cả các trường thông tin từ hóa đơn/biên lai trong ảnh dưới dạng đối tượng JSON.
Các trường BẮT BUỘC phải trích xuất:
- "Tên người bán"
- "Địa chỉ"
- "Ngày giao dịch"
- "Tổng tiền thanh toán" (Total Amount)
- "Danh sách món" (Mảng chứa "Tên món", "Đơn giá", "Số lượng")
"""
    max_tokens: int = 1024
    temperature: float = 0.0 

@app.on_event("startup")
async def load_model():
    """Tải mô hình lên GPU một lần duy nhất khi server khởi động."""
    global model, tokenizer
    
    # Tải Tokenizer
    try:
        tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH, trust_remote_code=True)
        
        # Tải Mô hình
        model = AutoModel.from_pretrained(
            LOCAL_MODEL_PATH,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            use_flash_attn=False,
        ).eval().cuda()
        
        print("✅ Mô hình InternVL đã tải thành công từ cục bộ lên GPU.")

    except Exception as e:
        print(f"LỖI KHỞI ĐỘNG MÔ HÌNH: {e}")
        # Dùng exit(1) để Docker biết server không khởi động được
        os._exit(1)
        
# API Endpoint Trích xuất Hóa đơn
@app.post("/extract_invoice")
async def extract_invoice(request: InferenceRequest):
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model chưa sẵn sàng.")

    try:
        # Tải ảnh từ URL
        response_img = requests.get(request.image_url, timeout=10)
        response_img.raise_for_status() 
        image_data = response_img.content
        
        # Tiền xử lý ảnh (sử dụng hàm load_image đã dán ở trên)
        pixel_values = load_image(image_data, max_num=6).to(torch.bfloat16).cuda()
        
        # Cấu hình Generation
        generation_config = dict(
            max_new_tokens=request.max_tokens, 
            do_sample=request.temperature > 0.0,
            temperature=request.temperature,
            num_beams=3, 
            repetition_penalty=3.5
        )
        
        # Chạy mô hình
        with torch.no_grad():
            response = model.chat(tokenizer, pixel_values, request.question, generation_config)

        # Trả về kết quả
        return {"status": "success", "extraction_result": response}

    except Exception as e:
        print(f"LỖI INFERENCE/REQUEST: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi xảy ra: {e}")
