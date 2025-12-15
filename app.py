import os
import io
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
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
# ĐƯỜNG DẪN MODEL - Tự động phát hiện môi trường
MODEL_NAME = "5CD-AI/Vintern-1B-v3_5"

# Kiểm tra đường dẫn Docker trước, nếu không có thì dùng đường dẫn local
DOCKER_MODEL_PATH = "/app/internvl_local"
LOCAL_MODEL_PATH = "internvl_local"

# Chọn đường dẫn phù hợp
if os.path.exists(DOCKER_MODEL_PATH):
    LOCAL_MODEL_PATH = DOCKER_MODEL_PATH
elif not os.path.exists(LOCAL_MODEL_PATH):
    # Nếu cả hai đều không tồn tại, tạo thư mục local
    os.makedirs(LOCAL_MODEL_PATH, exist_ok=True)

LOCAL_MODEL_PATH = os.path.abspath(LOCAL_MODEL_PATH) 

# Khởi tạo đối tượng model và tokenizer rỗng
model = None
tokenizer = None

# Khởi tạo Flask app với CORS
app = Flask(__name__)
CORS(app)  # Cho phép tất cả origins, có thể cấu hình chi tiết hơn nếu cần

def load_model():
    """Tải mô hình lên GPU một lần duy nhất khi server khởi động."""
    global model, tokenizer
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            LOCAL_MODEL_PATH, 
            trust_remote_code=True,
            local_files_only=True
        )
        
        model = AutoModel.from_pretrained(
            LOCAL_MODEL_PATH,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            use_flash_attn=False,
            local_files_only=True
        ).eval().cuda()

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise

# Load model sẽ được gọi trong __main__ block

# Endpoint root
@app.route('/', methods=['GET'])
def root():
    """Endpoint root để kiểm tra server."""
    return jsonify({
        "status": "success",
        "message": "InternVL Invoice Extraction API",
        "version": "1.0",
        "endpoints": {
            "health": "/health",
            "extract_invoice": "/extract_invoice"
        }
    }), 200

# Endpoint health check
@app.route('/health', methods=['GET'])
def health():
    """Kiểm tra trạng thái server và model."""
    model_status = "ready" if (model is not None and tokenizer is not None) else "not_ready"
    
    return jsonify({
        "status": "success",
        "server": "running",
        "model_status": model_status
    }), 200 if model_status == "ready" else 503

# Question mặc định cho trích xuất hóa đơn
DEFAULT_QUESTION = """<image>
Trích xuất tất cả các trường thông tin từ hóa đơn/biên lai trong ảnh dưới dạng đối tượng JSON.
Các trường BẮT BUỘC phải trích xuất:
- "Tên người bán"
- "Địa chỉ"
- "Ngày giao dịch"
- "Tổng tiền thanh toán" (Total Amount)
- "Danh sách món" (Mảng chứa "Tên món", "Đơn giá", "Số lượng")
"""

# API Endpoint Trích xuất Hóa đơn (chỉ cần ảnh)
@app.route('/extract_invoice', methods=['POST'])
def extract_invoice():
    """Trích xuất thông tin từ hóa đơn/biên lai. Chỉ cần gửi ảnh."""
    if model is None or tokenizer is None:
        return jsonify({
            "status": "error",
            "message": "Model chưa sẵn sàng."
        }), 503

    try:
        image_data = None
        
        # Kiểm tra xem có file upload không
        if 'image' in request.files:
            file = request.files['image']
            if file.filename == '':
                return jsonify({
                    "status": "error",
                    "message": "Không có file được chọn."
                }), 400
            image_data = file.read()
        
        # Nếu không có file upload, kiểm tra image_url
        elif request.is_json:
            data = request.get_json()
            
            if not data or 'image_url' not in data:
                return jsonify({
                    "status": "error",
                    "message": "Cần cung cấp 'image_url' (JSON) hoặc upload file 'image' (multipart/form-data)."
                }), 400
            
            image_url = data.get('image_url')
            response_img = requests.get(image_url, timeout=10)
            response_img.raise_for_status() 
            image_data = response_img.content
        else:
            return jsonify({
                "status": "error",
                "message": "Cần cung cấp 'image_url' (JSON) hoặc upload file 'image' (multipart/form-data)."
            }), 400
        
        if image_data is None:
            return jsonify({
                "status": "error",
                "message": "Không thể lấy dữ liệu ảnh."
            }), 400
        
        # Tiền xử lý ảnh
        pixel_values = load_image(image_data, max_num=6).to(torch.bfloat16).cuda()
        
        # Cấu hình Generation (mặc định)
        generation_config = dict(
            max_new_tokens=1024, 
            do_sample=False,
            temperature=0.0,
            num_beams=3, 
            repetition_penalty=3.5
        )
        
        # Chạy mô hình với question mặc định
        with torch.no_grad():
            response = model.chat(tokenizer, pixel_values, DEFAULT_QUESTION, generation_config)

        # Trả về kết quả
        return jsonify({
            "status": "success",
            "data": {
                "extraction_result": response
            }
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": f"Không thể tải ảnh từ URL: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Lỗi xảy ra: {str(e)}"
        }), 500

if __name__ == '__main__':
    try:
        load_model()
    except Exception as e:
        import traceback
        traceback.print_exc()
        os._exit(1)
    
    app.run(host='0.0.0.0', port=8000, debug=False)
