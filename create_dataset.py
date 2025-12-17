"""
Script tự động tạo dataset từ model InternVL
Chạy model trên tất cả ảnh trong UnBoundingDATASET và xuất ra Hugging Face Dataset hoặc CSV
"""
import os
import io
import csv
import json
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer
import sys

try:
    from datasets import Dataset, DatasetDict, Features, Value, Image as HFImage
    HF_DATASETS_AVAILABLE = True
except ImportError:
    HF_DATASETS_AVAILABLE = False
    print("⚠️  Hugging Face datasets không được cài đặt. Chỉ có thể xuất CSV.")
    print("   Cài đặt: pip install datasets")

# Set UTF-8 encoding cho Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Import các hàm từ app.py
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

    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
        i * j <= max_num and i * j >= min_num)
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size)

    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size
        )
        split_img = resized_img.crop(box)
        processed_images.append(split_img)
    assert len(processed_images) == blocks
    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images

def load_image(image_path, input_size=448, max_num=6):
    """Tải và tiền xử lý ảnh từ đường dẫn file."""
    image = Image.open(image_path).convert('RGB')
    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(img) for img in images]
    pixel_values = torch.stack(pixel_values)
    return pixel_values

def find_all_images(dataset_path):
    """Tìm tất cả file ảnh trong thư mục dataset."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    image_files = []
    
    if not os.path.exists(dataset_path):
        return image_files
    
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(os.path.join(root, file))
    
    return sorted(image_files)

def extract_invoice_info(model, tokenizer, image_path):
    """Trích xuất thông tin từ ảnh hóa đơn."""
    DEFAULT_QUESTION = """<image>
Trích xuất tất cả các trường thông tin từ hóa đơn/biên lai trong ảnh dưới dạng đối tượng JSON.
Các trường BẮT BUỘC phải trích xuất:
- "Tên người bán"
- "Địa chỉ"
- "Ngày giao dịch"
- "Tổng tiền thanh toán" (Total Amount)
- "Danh sách món" (Mảng chứa "Tên món", "Đơn giá", "Số lượng")
"""
    
    # Load và tiền xử lý ảnh
    pixel_values = load_image(image_path, max_num=6)
    if torch.cuda.is_available():
        pixel_values = pixel_values.to(torch.bfloat16).cuda()
    else:
        pixel_values = pixel_values.to(torch.float32)
    
    # Cấu hình Generation
    generation_config = dict(
        max_new_tokens=1024, 
        do_sample=False,
        temperature=0.0,
        num_beams=3, 
        repetition_penalty=3.5
    )
    
    # Chạy model
    with torch.no_grad():
        extraction_result = model.chat(tokenizer, pixel_values, DEFAULT_QUESTION, generation_config)
    
    return extraction_result

def parse_extraction_result(extraction_result):
    """Parse kết quả trích xuất từ model (có thể là JSON string hoặc dict)."""
    try:
        if isinstance(extraction_result, str):
            # Thử parse JSON
            if extraction_result.strip().startswith('{'):
                return json.loads(extraction_result)
            else:
                # Nếu không phải JSON, trả về text
                return {'raw_text': extraction_result}
        elif isinstance(extraction_result, dict):
            return extraction_result
        else:
            return {'raw_text': str(extraction_result)}
    except:
        return {'raw_text': str(extraction_result)}

def generate_conversations(extraction_result):
    """Tạo các câu hỏi và câu trả lời từ kết quả trích xuất."""
    conversations = []
    extracted_data = parse_extraction_result(extraction_result)
    
    # Câu hỏi mẫu dựa trên các trường thông tin
    question_answer_pairs = [
        ("Hóa đơn được xuất tại cửa hàng nào?", 
         extracted_data.get('Tên người bán') or extracted_data.get('Tên cửa hàng') or 'Không xác định'),
        ("Địa chỉ của cửa hàng là gì?", 
         extracted_data.get('Địa chỉ') or 'Không xác định'),
        ("Hóa đơn được xuất vào ngày nào?", 
         extracted_data.get('Ngày giao dịch') or extracted_data.get('Ngày bán') or 'Không xác định'),
        ("Tổng số tiền phải thanh toán là bao nhiêu?", 
         str(extracted_data.get('Tổng tiền thanh toán') or extracted_data.get('Tổng tiền') or 'Không xác định')),
        ("Khách hàng đã thanh toán bằng cách nào?", 
         'Tiền mặt' if extracted_data.get('Tiền mặt') or extracted_data.get('Tiền khách trả') else 'Không xác định')
    ]
    
    for question, answer in question_answer_pairs:
        conversations.append({'role': 'user', 'content': question})
        conversations.append({'role': 'assistant', 'content': str(answer)})
    
    return conversations

def process_all_images(dataset_path, model, tokenizer, output_path='dataset', output_format='hf'):
    """Xử lý tất cả ảnh và tạo dataset (Hugging Face hoặc CSV)."""
    image_files = find_all_images(dataset_path)
    
    if not image_files:
        print(f"❌ Không tìm thấy ảnh nào trong {dataset_path}")
        return
    
    print(f"[*] Tìm thấy {len(image_files)} ảnh")
    print(f"[*] Bắt đầu xử lý...")
    
    results = []
    
    for idx, image_path in enumerate(image_files, start=1):
        try:
            print(f"[{idx}/{len(image_files)}] Đang xử lý: {os.path.basename(image_path)}...")
            
            # Load ảnh PIL Image
            image = Image.open(image_path).convert('RGB')
            
            # Trích xuất thông tin
            extraction_result = extract_invoice_info(model, tokenizer, image_path)
            
            # Tạo description (tóm tắt)
            extracted_data = parse_extraction_result(extraction_result)
            
            description_parts = ["Hóa đơn bán hàng"]
            
            name = extracted_data.get('Tên người bán') or extracted_data.get('Tên cửa hàng')
            if name:
                description_parts.append(f"của {name}")
            
            date = extracted_data.get('Ngày giao dịch') or extracted_data.get('Ngày bán')
            if date:
                description_parts.append(f"ngày {date}")
            
            total = extracted_data.get('Tổng tiền thanh toán') or extracted_data.get('Tổng tiền')
            if total:
                description_parts.append(f"tổng tiền {total}")
            
            description = ", ".join(description_parts) if len(description_parts) > 1 else str(extraction_result)[:200]
            
            # Tạo conversations
            conversations = generate_conversations(extraction_result)
            
            # Format extractions
            if isinstance(extraction_result, dict):
                extractions_str = json.dumps(extraction_result, ensure_ascii=False)
            else:
                extractions_str = str(extraction_result)
            
            # Lưu kết quả (lưu cả PIL Image và đường dẫn để dễ xử lý sau)
            result = {
                'id': idx,
                'image': image,  # PIL Image cho HF Dataset
                'image_path': image_path,  # Đường dẫn cho CSV
                'description': description,
                'extractions': extractions_str,
                'conversations': json.dumps(conversations, ensure_ascii=False)
            }
            
            results.append(result)
            print(f"    ✅ Hoàn thành")
            
        except Exception as e:
            print(f"    ❌ Lỗi: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if not results:
        print("❌ Không có kết quả nào để lưu")
        return
    
    # Tạo dataset theo format
    if output_format == 'hf' and HF_DATASETS_AVAILABLE:
        print(f"\n[*] Đang tạo Hugging Face Dataset...")
        
        # Chuẩn bị data cho HF Dataset (bỏ image_path, chỉ giữ PIL Image)
        hf_results = []
        for result in results:
            hf_result = result.copy()
            hf_result.pop('image_path', None)  # Bỏ image_path, chỉ giữ PIL Image
            hf_results.append(hf_result)
        
        # Tạo Dataset từ results
        dataset = Dataset.from_list(hf_results)
        
        # Tạo DatasetDict với train split
        dataset_dict = DatasetDict({
            'train': dataset
        })
        
        # Lưu dataset
        dataset_dict.save_to_disk(output_path)
        
        print(f"✅ Đã tạo Hugging Face Dataset với {len(results)} mẫu")
        print(f"✅ Dataset được lưu tại: {output_path}")
        print(f"✅ Format: DatasetDict với train split")
        print(f"✅ Features: {list(dataset.features.keys())}")
        
    elif output_format == 'csv' or not HF_DATASETS_AVAILABLE:
        # Ghi vào CSV
        output_csv = output_path if output_path.endswith('.csv') else f"{output_path}.csv"
        print(f"\n[*] Đang ghi vào CSV: {output_csv}")
        
        # Chuyển đổi image từ PIL Image sang đường dẫn cho CSV
        csv_results = []
        for result in results:
            csv_result = {
                'id': result['id'],
                'image': result.get('image_path', ''),  # Dùng image_path thay vì PIL Image
                'description': result['description'],
                'extractions': result['extractions'],
                'conversations': result['conversations']
            }
            csv_results.append(csv_result)
        
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_results[0].keys())
            writer.writeheader()
            writer.writerows(csv_results)
        
        print(f"✅ Đã tạo CSV với {len(results)} mẫu")
        print(f"✅ File CSV: {output_csv}")
    
    return results

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Tạo dataset từ model InternVL')
    parser.add_argument('dataset_path', nargs='?', help='Đường dẫn đến thư mục UnBoundingDATASET')
    parser.add_argument('--output', default='dataset', help='Tên file/directory output (mặc định: dataset)')
    parser.add_argument('--format', choices=['hf', 'csv', 'both'], default='hf', 
                       help='Format output: hf (Hugging Face Dataset), csv, hoặc both (mặc định: hf)')
    parser.add_argument('--model_path', default='internvl_local', help='Đường dẫn đến model (mặc định: internvl_local)')
    
    args = parser.parse_args()
    
    # Đường dẫn dataset
    if args.dataset_path:
        DATASET_PATH = args.dataset_path
    else:
        possible_paths = [
            "UnBoundingDATASET",
            "../UnBoundingDATASET",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "UnBoundingDATASET")
        ]
        
        DATASET_PATH = None
        for path in possible_paths:
            if os.path.exists(path):
                DATASET_PATH = os.path.abspath(path)
                break
        
        if DATASET_PATH is None:
            print("❌ Không tìm thấy thư mục UnBoundingDATASET")
            print("   Vui lòng chỉ định đường dẫn: python create_dataset.py <đường_dẫn_UnBoundingDATASET>")
            return 1
    
    DATASET_PATH = os.path.abspath(DATASET_PATH)
    MODEL_PATH = os.path.abspath(args.model_path)
    
    print("="*60)
    print("TẠO DATASET TỪ MODEL INTERNVL")
    print("="*60)
    print(f"Dataset path: {DATASET_PATH}")
    print(f"Model path: {MODEL_PATH}")
    print(f"Output: {args.output}")
    print(f"Format: {args.format}")
    print("="*60)
    
    if args.format == 'hf' and not HF_DATASETS_AVAILABLE:
        print("\n⚠️  Hugging Face datasets không có sẵn, sẽ xuất CSV thay thế")
        args.format = 'csv'
    
    # Load model
    print("\n[*] Đang load model...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_PATH, 
            trust_remote_code=True,
            local_files_only=True
        )
        
        model = AutoModel.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
            use_flash_attn=False,
            local_files_only=True
        ).eval()
        
        if torch.cuda.is_available():
            model = model.cuda()
        
        print("✅ Model đã load thành công")
    except Exception as e:
        print(f"❌ Lỗi load model: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Xử lý tất cả ảnh
    if args.format == 'both':
        # Tạo cả hai format - cần xử lý riêng để có cả PIL Image và đường dẫn
        print("\n[*] Tạo cả Hugging Face Dataset và CSV...")
        # Tạo HF Dataset trước
        process_all_images(DATASET_PATH, model, tokenizer, args.output, 'hf')
        # Sau đó tạo CSV từ cùng kết quả (cần load lại ảnh để lấy đường dẫn)
        csv_output = args.output if args.output.endswith('.csv') else f"{args.output}.csv"
        process_all_images(DATASET_PATH, model, tokenizer, csv_output, 'csv')
    else:
        process_all_images(DATASET_PATH, model, tokenizer, args.output, args.format)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Bị hủy bởi người dùng")
        sys.exit(1)
