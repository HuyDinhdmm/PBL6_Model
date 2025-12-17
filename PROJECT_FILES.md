# Danh Sách Files Trong Project

## 📁 Files Chính (Core Files)

### API Server
- ✅ `app.py` - Flask server chính với queue system
- ✅ `requirements.txt` - Python dependencies
- ✅ `Dockerfile` - Docker configuration cho GPU

### Deployment
- ✅ `deploy_vastai.sh` - Script deploy lên Vast.ai
- ✅ `download_model.py` - Script tải model từ Hugging Face

### Documentation
- ✅ `README.md` - Hướng dẫn chính
- ✅ `HUONG_DAN_VASTAI.md` - Hướng dẫn chi tiết Vast.ai
- ✅ `QUICKSTART_VASTAI.md` - Quick start guide

### Testing
- ✅ `test_api.py` - Script test API với ảnh ngẫu nhiên từ dataset

### Utilities
- ✅ `create_dataset.py` - Script tạo dataset từ model
- ✅ `kaggle_dataset_creation.ipynb` - Notebook cho Kaggle

### Configuration
- ✅ `.gitignore` - Git ignore rules

## 📁 Thư Mục

### Model Files (Không commit)
- `internvl_local/` - Model files (lớn, trong .gitignore)

### Dataset (Không commit)
- `UnBoundingDATASET/` - Dataset ảnh (lớn, trong .gitignore)
- `UnBoundingDATASET.zip` - Dataset zip (lớn, trong .gitignore)

### Virtual Environment (Không commit)
- `pbl/` - Python virtual environment (trong .gitignore)

## 🔒 Files Được Bảo Vệ

Tất cả files trong `.gitignore` vẫn tồn tại trên máy local, chỉ không được commit lên Git:
- ✅ `internvl_local/` - Model vẫn còn
- ✅ `UnBoundingDATASET/` - Dataset vẫn còn
- ✅ `pbl/` - Virtual environment vẫn còn

## 📝 Lưu Ý

- **KHÔNG XÓA** bất kỳ file nào trong danh sách trên
- Files trong `.gitignore` vẫn cần thiết cho local development
- Chỉ không commit lên Git (để tránh repo quá lớn)

