# Backend Setup Guide (Miniconda)

## 1. Create and Activate Environment

```bash
# Create a new environment named 'video_gen' with Python 3.10
conda create -n video_gen python=3.10

# Activate the environment
conda activate video_gen
```

## 2. Install Dependencies

Navigate to the `backend` directory and install the required packages:

```bash
cd backend
pip install -r requirements.txt
```

## 3. Install Playwright Browsers (Optional)

If you have Chrome installed, you can skip this. If not, or if you encounter errors, run:

```bash
playwright install chromium
```

## 4. Run the Server

**Important**: You must run the server from the **root directory** (the parent of `backend`), NOT inside the `backend` folder itself, so that Python can correctly import the `backend` module.

```bash
# If you are currently in the 'backend' folder, go up one level:
cd ..

# Run the server from the root directory:
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
