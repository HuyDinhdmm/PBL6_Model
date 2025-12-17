#!/usr/bin/env python3
"""
Script test API InternVL Invoice Extraction
Test tất cả endpoints và hiển thị response đầy đủ
Tự động lấy ngẫu nhiên ảnh từ UnBoundingDATASET
"""

import requests
import json
import sys
import argparse
import random
import os
from pathlib import Path

# Màu sắc cho terminal (nếu hỗ trợ)
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color=Colors.RESET):
    """In text với màu"""
    try:
        print(f"{color}{text}{Colors.RESET}")
    except:
        print(text)

def print_section(title):
    """In section header"""
    print_colored(f"\n{'='*60}", Colors.CYAN)
    print_colored(f"  {title}", Colors.BOLD + Colors.CYAN)
    print_colored(f"{'='*60}", Colors.CYAN)

def print_response(response, endpoint):
    """In response đầy đủ"""
    print_colored(f"\n📡 Endpoint: {endpoint}", Colors.BLUE)
    print_colored(f"   Status Code: {response.status_code}", 
                  Colors.GREEN if response.status_code == 200 else Colors.RED)
    print_colored(f"   Headers:", Colors.YELLOW)
    for key, value in response.headers.items():
        print(f"      {key}: {value}")
    
    print_colored(f"\n   Response Body:", Colors.YELLOW)
    try:
        # Thử parse JSON
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        # Nếu không phải JSON, in raw text
        print(response.text[:1000])  # Giới hạn 1000 ký tự
        if len(response.text) > 1000:
            print(f"\n   ... (truncated, total length: {len(response.text)} chars)")

def test_health(base_url):
    """Test health endpoint"""
    print_section("1. Health Check")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print_response(response, "GET /health")
        return response.status_code == 200
    except Exception as e:
        print_colored(f"❌ Lỗi: {e}", Colors.RED)
        return False

def test_root(base_url):
    """Test root endpoint"""
    print_section("2. Root Endpoint")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print_response(response, "GET /")
        return response.status_code == 200
    except Exception as e:
        print_colored(f"❌ Lỗi: {e}", Colors.RED)
        return False

def test_extract_invoice_with_url(base_url, image_url):
    """Test extract_invoice với image_url"""
    print_section("3. Extract Invoice (Image URL)")
    try:
        data = {
            "image_url": image_url
        }
        print_colored(f"   Request:", Colors.YELLOW)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        response = requests.post(
            f"{base_url}/extract_invoice",
            json=data,
            timeout=120  # 2 phút cho inference
        )
        print_response(response, "POST /extract_invoice (image_url)")
        return response.status_code == 200
    except Exception as e:
        print_colored(f"❌ Lỗi: {e}", Colors.RED)
        return False

def test_extract_invoice_with_file(base_url, image_path):
    """Test extract_invoice với file upload"""
    print_section("4. Extract Invoice (File Upload)")
    try:
        if not Path(image_path).exists():
            print_colored(f"❌ File không tồn tại: {image_path}", Colors.RED)
            return False
        
        print_colored(f"   Upload file: {image_path}", Colors.YELLOW)
        
        with open(image_path, 'rb') as f:
            files = {'image': (Path(image_path).name, f, 'image/jpeg')}
            response = requests.post(
                f"{base_url}/extract_invoice",
                files=files,
                timeout=120  # 2 phút cho inference
            )
        
        print_response(response, "POST /extract_invoice (file upload)")
        return response.status_code == 200
    except Exception as e:
        print_colored(f"❌ Lỗi: {e}", Colors.RED)
        return False

def find_random_image(dataset_path):
    """Tìm ảnh ngẫu nhiên từ thư mục dataset"""
    if not os.path.exists(dataset_path):
        return None
    
    # Tìm tất cả file ảnh
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    image_files = []
    
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in image_extensions):
                image_files.append(os.path.join(root, file))
    
    if not image_files:
        return None
    
    # Chọn ngẫu nhiên
    return random.choice(image_files)

def main():
    parser = argparse.ArgumentParser(
        description='Test API InternVL Invoice Extraction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  # Test tự động với ảnh ngẫu nhiên từ UnBoundingDATASET
  python test_api.py --url http://localhost:8000
  
  # Test với image URL cụ thể
  python test_api.py --url http://localhost:8000 --image-url https://example.com/invoice.jpg
  
  # Test với file ảnh cụ thể
  python test_api.py --url http://localhost:8000 --image-file ./invoice.jpg
  
  # Chỉ định đường dẫn dataset
  python test_api.py --url http://localhost:8000 --dataset-path ./UnBoundingDATASET
        """
    )
    
    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='URL của API server (default: http://localhost:8000)'
    )
    
    parser.add_argument(
        '--image-url',
        help='URL của ảnh để test extract_invoice'
    )
    
    parser.add_argument(
        '--image-file',
        help='Đường dẫn file ảnh để test extract_invoice'
    )
    
    parser.add_argument(
        '--dataset-path',
        default='UnBoundingDATASET',
        help='Đường dẫn đến thư mục UnBoundingDATASET (default: UnBoundingDATASET)'
    )
    
    parser.add_argument(
        '--no-random-image',
        action='store_true',
        help='Không tự động lấy ảnh ngẫu nhiên từ dataset'
    )
    
    args = parser.parse_args()
    
    base_url = args.url.rstrip('/')
    
    print_colored("\n" + "="*60, Colors.CYAN)
    print_colored("  🧪 TEST API INTERNVL INVOICE EXTRACTION", Colors.BOLD + Colors.CYAN)
    print_colored("="*60, Colors.CYAN)
    print_colored(f"\n📍 Server: {base_url}", Colors.BLUE)
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health(base_url)))
    
    # Test 2: Root endpoint
    results.append(("Root Endpoint", test_root(base_url)))
    
    # Tự động tìm ảnh ngẫu nhiên nếu không có image-url hoặc image-file
    random_image = None
    if not args.image_url and not args.image_file and not args.no_random_image:
        print_colored(f"\n🔍 Đang tìm ảnh ngẫu nhiên từ {args.dataset_path}...", Colors.YELLOW)
        random_image = find_random_image(args.dataset_path)
        if random_image:
            print_colored(f"✅ Đã chọn ảnh: {os.path.basename(random_image)}", Colors.GREEN)
            print_colored(f"   Đường dẫn: {random_image}", Colors.CYAN)
        else:
            print_colored(f"⚠️  Không tìm thấy ảnh trong {args.dataset_path}", Colors.YELLOW)
            print_colored("   Sẽ bỏ qua test extract_invoice", Colors.YELLOW)
    
    # Test 3: Extract invoice với image_url
    if args.image_url:
        results.append(("Extract Invoice (URL)", test_extract_invoice_with_url(base_url, args.image_url)))
    
    # Test 4: Extract invoice với file upload (ưu tiên random image nếu có)
    image_to_test = args.image_file or random_image
    if image_to_test:
        results.append(("Extract Invoice (File)", test_extract_invoice_with_file(base_url, image_to_test)))
    
    # Tổng kết
    print_section("📊 Tổng Kết")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        color = Colors.GREEN if result else Colors.RED
        print_colored(f"   {status} - {name}", color)
    
    print_colored(f"\n   Kết quả: {passed}/{total} tests passed", 
                  Colors.GREEN if passed == total else Colors.YELLOW)
    
    if passed == total:
        print_colored("\n🎉 Tất cả tests đều PASS!", Colors.GREEN + Colors.BOLD)
        return 0
    else:
        print_colored(f"\n⚠️  Có {total - passed} test(s) FAILED", Colors.RED + Colors.BOLD)
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_colored("\n\n⚠️  Test bị hủy bởi người dùng", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n\n❌ Lỗi không mong đợi: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)

