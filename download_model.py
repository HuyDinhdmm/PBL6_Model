"""
Script để tải model InternVL từ Hugging Face Hub
Model: 5CD-AI/Vintern-1B-v3_5
"""
import os
import sys
from huggingface_hub import snapshot_download

# Set UTF-8 encoding cho Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Đường dẫn thư mục model local
MODEL_DIR = "internvl_local"
MODEL_ID = "5CD-AI/Vintern-1B-v3_5"

def download_model():
    """Tải model từ Hugging Face Hub về thư mục local."""
    print(f"[*] Dang tai model {MODEL_ID} tu Hugging Face Hub...")
    print(f"[*] Thu muc dich: {os.path.abspath(MODEL_DIR)}")
    
    try:
        # Tải toàn bộ model (bao gồm config, tokenizer, weights)
        snapshot_download(
            repo_id=MODEL_ID,
            local_dir=MODEL_DIR
        )
        
        print(f"[+] Tai model thanh cong!")
        print(f"[+] Model da duoc luu tai: {os.path.abspath(MODEL_DIR)}")
        
    except Exception as e:
        print(f"[-] Loi khi tai model: {e}")
        print("\n[!] Goi y:")
        print("1. Kiem tra ket noi internet")
        print("2. Dam bao da cai dat: pip install huggingface_hub")
        print("3. Neu can, dang nhap Hugging Face: huggingface-cli login")
        raise

if __name__ == "__main__":
    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    download_model()
