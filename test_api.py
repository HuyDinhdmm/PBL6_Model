"""
Script test API InternVL với ảnh ngẫu nhiên từ dataset
"""
import os
import random
import requests
import json
import sys
import argparse

# Cấu hình mặc định
DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT = 120

def find_all_images(dataset_path):
    """Tìm tất cả file ảnh trong thư mục dataset (bao gồm subdirectories)."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    image_files = []
    
    if not os.path.exists(dataset_path):
        return image_files
    
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(os.path.join(root, file))
    
    return image_files

def test_api_with_random_image(dataset_path, base_url=DEFAULT_BASE_URL, use_file_upload=True):
    """
    Test API với ảnh ngẫu nhiên từ dataset.
    
    Args:
        dataset_path: Đường dẫn đến thư mục UnBoundingDATASET
        base_url: URL của API server
        use_file_upload: Sử dụng file upload (True) hoặc image_url (False)
    
    Returns:
        dict: Kết quả test
    """
    image_files = find_all_images(dataset_path)
    
    if not image_files:
        return {
            "success": False,
            "error": f"Không tìm thấy ảnh nào trong {dataset_path}"
        }
    
    selected_image = random.choice(image_files)
    print(f"[*] Đang xử lý ảnh: {os.path.basename(selected_image)}...")
    
    try:
        if use_file_upload:
            # Dùng file upload
            with open(selected_image, 'rb') as f:
                files = {'image': (os.path.basename(selected_image), f, 'image/jpeg')}
                response = requests.post(
                    f"{base_url}/extract_invoice",
                    files=files,
                    timeout=TIMEOUT
                )
        else:
            # Dùng image_url (cần HTTP server để serve ảnh)
            return {
                "success": False,
                "error": "Image URL mode chưa được implement. Vui lòng dùng file upload."
            }
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "image_path": selected_image,
                "status_code": response.status_code,
                "response": data
            }
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', response.text)
            except:
                error_msg = response.text
            return {
                "success": False,
                "image_path": selected_image,
                "status_code": response.status_code,
                "error": error_msg
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"Request timeout (quá {TIMEOUT} giây)",
            "image_path": selected_image
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "image_path": selected_image
        }

def main():
    """Hàm main chạy test"""
    parser = argparse.ArgumentParser(description='Test API InternVL với ảnh ngẫu nhiên từ dataset')
    parser.add_argument('dataset_path', nargs='?', help='Đường dẫn đến thư mục UnBoundingDATASET')
    parser.add_argument('--url', default=DEFAULT_BASE_URL, help=f'URL của API server (mặc định: {DEFAULT_BASE_URL})')
    
    args = parser.parse_args()
    
    BASE_URL = args.url
    
    # Kiểm tra API server
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('model_status') != 'ready':
                print("⚠️  Model chưa sẵn sàng, có thể gặp lỗi khi test")
    except requests.exceptions.ConnectionError:
        print("❌ Không thể kết nối đến API server!")
        print(f"   Hãy đảm bảo server đang chạy: python app.py")
        return 1
    except Exception as e:
        print(f"⚠️  Lỗi khi kiểm tra server: {e}")
    
    # Đường dẫn dataset
    if args.dataset_path:
        DATASET_PATH = args.dataset_path
    else:
        possible_paths = [
            "UnBoundingDATASET",
            "../UnBoundingDATASET",
            "../../UnBoundingDATASET",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "UnBoundingDATASET")
        ]
        
        DATASET_PATH = None
        for path in possible_paths:
            if os.path.exists(path):
                DATASET_PATH = os.path.abspath(path)
                break
        
        if DATASET_PATH is None:
            print("\n❌ Không tìm thấy thư mục UnBoundingDATASET")
            print("   Vui lòng chỉ định đường dẫn:")
            print("   python test_api.py <đường_dẫn_UnBoundingDATASET> [--url <API_URL>]")
            print("\n   Ví dụ:")
            print("   python test_api.py ./UnBoundingDATASET")
            print("   python test_api.py ./UnBoundingDATASET --url http://54.123.45.67:8000")
            return 1
    
    DATASET_PATH = os.path.abspath(DATASET_PATH)
    
    # Test với ảnh ngẫu nhiên
    result = test_api_with_random_image(DATASET_PATH, BASE_URL, use_file_upload=True)
    
    # Hiển thị kết quả
    if result["success"]:
        response_data = result.get('response', {})
        if response_data.get('status') == 'success':
            extraction_result = response_data.get('data', {}).get('extraction_result', '')
            
            # Lưu kết quả vào file JSON
            output_file = f"result_{os.path.basename(result['image_path'])}.json"
            output_data = {
                "image_path": result['image_path'],
                "status_code": result['status_code'],
                "extraction_result": extraction_result,
                "full_response": response_data
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Thành công! Đã lưu kết quả vào: {output_file}")
        else:
            print(f"❌ Lỗi: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
    else:
        print(f"❌ Lỗi: {result.get('error', 'Unknown error')}")
    
    return 0 if result["success"] else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test bị hủy bởi người dùng")
        sys.exit(1)
