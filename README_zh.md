# 📋 会议助手

一个全栈应用，使用 FastAPI、FunASR 和 Streamlit，实现会议音频转写并生成结构化会议纪要。🚀

![Streamlit 界面](images/meeting_assistant.jpeg)

## ✨ 功能亮点

|  表情 | 功能              | 描述                                                 |
| :-: | :-------------- | :------------------------------------------------- |
|  🎙 | **异步音频转写**      | 上传音频文件，后台使用 FunASR 进行异步转写。                         |
|  🔊 | **说话人识别与格式化**   | 自动识别说话人，合并连续片段并格式化时间戳。                             |
|  ✍️ | **交互式编辑**       | 使用 Streamlit ACE 编辑器编辑原始转写文本，映射说话人标签到真实姓名。         |
|  🤖 | **AI 自动生成会议纪要** | 调用大模型（如 Qwen、OpenAI）生成结构化 Markdown 会议纪要，并支持自定义提示词。 |
|  📥 | **导出 Markdown** | 将最终生成的会议纪要以 Markdown 文件形式下载。                       |

## 🚀 安装指南

按照以下步骤创建环境并安装依赖：

```bash
# 创建 Conda 环境
echo "正在创建 meeting_assistant 环境..."
mamba create -n meeting_assistant python=3.10 -c conda-forge -y
conda activate meeting_assistant

# 安装依赖
pip install torch torchvision torchaudio \
    -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
pip install funasr openai streamlit streamlit-ace \
    -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
mamba install fastapi uvicorn python-dotenv requests librosa ffmpeg onnxruntime -c conda-forge -y
```

## ⚙️ 配置说明

复制模板 `.env.example` 为 `.env` 并修改：

```env
# 后端配置
APP_PORT_BACKEND=8401
ASR_MODEL_NAME="damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
ASR_VAD_MODEL="fsmn-vad"
ASR_VAD_MODEL_REVISION="v2.0.4"
ASR_PUNC_MODEL="ct-punc"
ASR_PUNC_MODEL_REVISION="v2.0.4"
ASR_SPK_MODEL="cam++"
ASR_SPK_MODEL_REVISION="v2.0.2"
ASR_DEVICE="cuda"

# 前端配置
BACKEND_API_URL="localhost"
LLM_API_URL="https://api.openai.com/v1/chat/completions"
LLM_API_KEY="你的_API_KEY"
LLM_MODEL_NAME="gpt4.1-mini"
```

> 确保 `BACKEND_API_URL` 与后端主机（如 `localhost` 或容器名称）一致。

## 🏃‍♂️ 启动应用

### 1. 启动后端服务

```bash
# 运行主脚本
python main.py
# 或使用 Uvicorn
uvicorn main:app --host 0.0.0.0 --port $APP_PORT_BACKEND --reload
```

启动日志示例：

```
Loading ASR model...
Initializing FunASR AutoModel...
ASR model loaded successfully.
Startup complete.
```

### 2. 启动前端界面

```bash
# 中文界面
streamlit run app.py

# 英文界面
streamlit run app2.py
```

在浏览器打开 Streamlit 提示的地址（如 `http://localhost:8501`）。🌐

## 🛠 使用流程

1. **上传录音** 🎧：步骤1 – 选择并上传会议音频文件（wav/mp3/m4a/ogg/flac）。
2. **开始转写** 🕒：步骤2 – 提交后端异步转写任务并等待完成。
3. **编辑与映射** ✏️：步骤3 – 在编辑器中修正转写文本，映射说话人标签到真实姓名。
4. **生成纪要** 📝：步骤4 – 调用 LLM 生成结构化 Markdown 会议纪要。
5. **下载结果** 💾：下载生成的 Markdown 会议纪要文件。

## 📡 API 接口

* `POST /api/transcribe`：上传音频文件，返回 `task_id`。
* `GET /api/job/{task_id}`：查询转写状态并获取结果。
* `GET /`：服务健康检查。