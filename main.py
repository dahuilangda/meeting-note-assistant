import asyncio
import os
import tempfile
import uuid
from typing import Dict, Any, Set, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, status
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Import FunASR and Starlette Concurrency ---
try:
    from funasr import AutoModel
    from starlette.concurrency import run_in_threadpool
except ImportError:
    print("Error: funasr library not found. Please install it using 'pip install funasr starlette'")
    AutoModel = None
    run_in_threadpool = None # Mark as unavailable

# --- Configuration from Environment Variables ---
ASR_MODEL_NAME = os.getenv("ASR_MODEL_NAME", "damo/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch")
ASR_VAD_MODEL = os.getenv("ASR_VAD_MODEL", "fsmn-vad")
ASR_VAD_MODEL_REVISION = os.getenv("ASR_VAD_MODEL_REVISION", "v2.0.4")
ASR_PUNC_MODEL = os.getenv("ASR_PUNC_MODEL", "ct-punc")
ASR_PUNC_MODEL_REVISION = os.getenv("ASR_PUNC_MODEL_REVISION", "v2.0.4")
ASR_SPK_MODEL = os.getenv("ASR_SPK_MODEL", "cam++")
ASR_SPK_MODEL_REVISION = os.getenv("ASR_SPK_MODEL_REVISION", "v2.0.2")
ASR_DEVICE = os.getenv("ASR_DEVICE")
# --- End Configuration ---

# Global variables for models
asr_model: Optional[AutoModel] = None

# In-memory storage for tasks
tasks: Dict[str, Dict[str, Any]] = {}

# --- Pydantic Models (Updated) ---
class ProcessAudioResponse(BaseModel):
    task_id: str
    status: str
    detail: str = "Processing started."

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    transcription: Optional[str] = None
    error: Optional[str] = None

def format_recognition_result(res) -> tuple[str, Set[str]]:
    """
    扁平化所有 sentence_info，然后按时间顺序合并同一说话人连续句子，
    并且不输出“语音识别结果：”标题，直接以“说话人 X [start-end]: 文本”开头。
    """
    all_speakers = set()
    if not res:
        return "No transcription results were returned.", all_speakers

    sentences = []
    for item in res:
        sentences.extend(item.get("sentence_info", []))

    formatted_output = []
    current_speaker = None
    buffer_text: list[str] = []
    buf_start = buf_end = 0.0

    for sent in sentences:
        spk = sent.get("spk", "未知")
        txt = sent.get("text", "").strip()
        start_ms = sent.get("start")
        end_ms   = sent.get("end")
        if txt == "" or start_ms is None or end_ms is None:
            continue
        start_s = start_ms / 1000
        end_s   = end_ms   / 1000
        all_speakers.add(spk)

        if spk == current_speaker:
            buffer_text.append(txt)
            buf_end = end_s
        else:
            if buffer_text:
                formatted_output.append(
                    f"说话人 {current_speaker} [{buf_start:.2f}s - {buf_end:.2f}s]: "
                    + " ".join(buffer_text)
                )
            current_speaker = spk
            buffer_text = [txt]
            buf_start = start_s
            buf_end   = end_s

    if buffer_text:
        formatted_output.append(
            f"说话人 {current_speaker} [{buf_start:.2f}s - {buf_end:.2f}s]: "
            + " ".join(buffer_text)
        )

    return "\n".join(formatted_output), all_speakers

# --- Background Task Function ---
async def async_process_audio_task(task_id: str, temp_file_path: str, original_filename: str):
    tasks[task_id]["status"] = "PROCESSING"
    transcription = None
    error = None

    try:
        if asr_model is None or run_in_threadpool is None:
             raise RuntimeError("ASR model or thread pool executor is not available.")

        print(f"[{task_id}] Starting ASR for '{original_filename}'...")
        asr_res = await run_in_threadpool(
            asr_model.generate,
            input=temp_file_path,
            batch_size_s=300,
            hotword=''
        )
        print(f"[{task_id}] ASR completed.")

        tasks[task_id]["status"] = "FORMATTING_TRANSCRIPTION"
        if not asr_res:
             transcription = "Transcription result is empty or invalid."
             print(f"[{task_id}] funasr returned empty result.")
        else:
            transcription, speakers = format_recognition_result(asr_res)
            print(f"[{task_id}] Formatted transcription generated.")

        tasks[task_id]["transcription"] = transcription
        tasks[task_id]["status"] = "COMPLETED"
        print(f"[{task_id}] Task completed successfully (Transcription Ready).")

    except Exception as e:
        error = f"Error during ASR transcription: {e}"
        tasks[task_id]["status"] = "FAILED"
        tasks[task_id]["error"] = error
        if 'transcription' not in tasks[task_id]:
             tasks[task_id]['transcription'] = "Transcription failed."
        print(f"[{task_id}] Task failed with error: {error}")

    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"[{task_id}] Cleaned up temporary file: {temp_file_path}")
            except OSError as e:
                print(f"[{task_id}] Error removing temporary file {temp_file_path}: {e}")
        if "temp_file" in tasks[task_id]:
             del tasks[task_id]["temp_file"]


# --- FastAPI App and Endpoints ---
app = FastAPI(
    title="Meeting Audio Transcription API",
    description="API to transcribe audio files using FunASR with async task processing."
)

@app.on_event("startup")
async def startup_event():
    global asr_model
    print("Loading ASR model...")

    if AutoModel is None or run_in_threadpool is None:
        print("funasr or starlette.concurrency not found. ASR functionality will be disabled.")
    else:
        try:
            print("Initializing FunASR AutoModel...")
            model_kwargs = {
                "model": ASR_MODEL_NAME,
                "vad_model": ASR_VAD_MODEL,
                "vad_model_revision": ASR_VAD_MODEL_REVISION,
                "punc_model": ASR_PUNC_MODEL,
                "punc_model_revision": ASR_PUNC_MODEL_REVISION,
                "spk_model": ASR_SPK_MODEL,
                "spk_model_revision": ASR_SPK_MODEL_REVISION,
                "disable_update": True,
            }
            if ASR_DEVICE:
                model_kwargs["device"] = ASR_DEVICE

            asr_model = AutoModel(**model_kwargs)
            print("ASR model loaded successfully.")

        except Exception as e:
            print(f"Error during ASR model loading: {e}")
            asr_model = None
    print("Startup complete.")


@app.on_event("shutdown")
async def shutdown_event():
    global asr_model
    print("Shutting down...")
    asr_model = None
    print("Shutdown complete.")


@app.post(
    "/api/transcribe",
    response_model=ProcessAudioResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit audio for transcription",
    description="Upload an audio file. The transcription runs in the background. Returns a task ID to query the status and results."
)
async def process_audio_endpoint(file: UploadFile = File(..., description="Audio file of the meeting")):
    if asr_model is None or run_in_threadpool is None:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail="ASR service is not loaded or available. Check server logs for startup errors."
         )

    task_id = uuid.uuid4().hex
    temp_file_path = None
    try:
        file_extension = os.path.splitext(file.filename)[1]
        if not file_extension:
             file_extension = ".wav"
        if not file_extension.startswith('.'):
             file_extension = '.' + file_extension

        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            temp_file_path = tmp_file.name

        tasks[task_id] = {
            "task_id": task_id,
            "status": "SAVED_FILE",
            "transcription": None,
            "error": None,
            "temp_file": temp_file_path,
        }
        print(f"[{task_id}] Saved file to {temp_file_path}. Starting background task.")
        asyncio.create_task(async_process_audio_task(task_id, temp_file_path, file.filename))
        return ProcessAudioResponse(task_id=task_id, status=tasks[task_id]["status"])

    except Exception as e:
        current_task_id = locals().get('task_id', 'N/A')
        if temp_file_path and os.path.exists(temp_file_path):
             try:
                 os.remove(temp_file_path)
                 print(f"[{current_task_id}] Cleaned up temporary file due to error: {temp_file_path}")
             except OSError as oe:
                  print(f"[{current_task_id}] Error removing temporary file after exception {temp_file_path}: {oe}")

        if current_task_id != 'N/A' and current_task_id in tasks:
             tasks[current_task_id]["status"] = "FAILED"
             tasks[current_task_id]["error"] = f"Failed during file saving or task initiation: {e}"
             tasks[current_task_id]["transcription"] = f"Initialization failed: {e}" if tasks[current_task_id].get("transcription") is None else tasks[current_task_id]["transcription"]
        else:
             print(f"Error before task ID {current_task_id} generated or task not in dict: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start audio processing task: {e}"
        )


@app.get(
    "/api/job/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get status and transcription of an audio processing task",
    description="Query the status of a submitted audio processing task using its ID. Returns transcription when completed."
)
async def get_task_status(task_id: str):
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task ID not found.")
    return TaskStatusResponse(
        task_id=task.get("task_id"),
        status=task.get("status"),
        transcription=task.get("transcription"),
        error=task.get("error")
    )

@app.get("/")
async def read_root():
    return {"message": "Meeting Audio Transcription API is running. Use /api/transcribe to submit audio and /api/job/{task_id} to check progress."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT_BACKEND", 8401))
    uvicorn.run(app, host="0.0.0.0", port=port)