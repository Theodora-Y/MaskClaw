# model_server/minicpm_api.py
import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor, AutoTokenizer
from fastapi import FastAPI, UploadFile, File, Form
import uvicorn
import io
import os
from pathlib import Path

app = FastAPI()

# 1. 解析本地模型路径（与启动目录无关）
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "OpenBMB" / "MiniCPM-V-4_5"
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL_PATH))).expanduser().resolve()

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"本地模型目录不存在: {MODEL_PATH}. "
        "请检查 MODEL_PATH 环境变量或项目目录结构。"
    )

print("正在加载 MiniCPM-V-4_5 视觉模型到 GPU，请稍候...")
model = AutoModelForCausalLM.from_pretrained(
    str(MODEL_PATH),
    trust_remote_code=True,
    torch_dtype=torch.bfloat16,
    local_files_only=True,
)
tokenizer = AutoTokenizer.from_pretrained(str(MODEL_PATH), trust_remote_code=True, local_files_only=True)
processor = AutoProcessor.from_pretrained(str(MODEL_PATH), trust_remote_code=True, local_files_only=True)
model = model.cuda().eval()  # 放入显卡
print("模型加载成功！API 服务已启动。")

# 2. 定义处理接口
@app.post("/chat")
async def chat_with_minicpm(
    prompt: str = Form(...), 
    image: UploadFile = File(None)
):
    try:
        # 如果有图片，读取图片
        img = None
        if image:
            image_data = await image.read()
            img = Image.open(io.BytesIO(image_data)).convert('RGB')
        
        # 使用 MiniCPMV 的 chat 方法
        msgs = [{"role": "user", "content": [img, prompt] if img else prompt}]
        
        with torch.no_grad():
            response = model.chat(
                image=img,
                msgs=msgs,
                tokenizer=tokenizer,
                processor=processor
            )
        
        return {"status": "success", "response": response}
    
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

if __name__ == '__main__':
    # 启动 API 服务，运行在本地 8000 端口
    uvicorn.run(app, host='127.0.0.1', port=8000)