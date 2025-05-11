import streamlit as st
from streamlit_ace import st_ace
import requests
import time
import re
import datetime
from typing import Tuple, List, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration from Environment Variables ---
BACKEND_API_URL = os.getenv("BACKEND_API_URL")
APP_PORT_BACKEND = os.getenv("APP_PORT_BACKEND")
DEFAULT_LLM_API_URL = os.getenv("LLM_API_URL")
DEFAULT_LLM_API_KEY = os.getenv("LLM_API_KEY")
DEFAULT_LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")
# --- End Configuration ---


# --- Session State Initialization ---
def init_session_state():
    st.session_state.setdefault('meeting_info', {
        'topic': '',
        'date': datetime.date.today(),
        'time': datetime.datetime.now().time(),
        'location': ''
    })
    st.session_state.setdefault('uploaded_audio', None)
    st.session_state.setdefault('task_id', None)
    st.session_state.setdefault('task_status', 'idle')
    st.session_state.setdefault('raw_transcription', '')
    st.session_state.setdefault('editable_transcription', '')
    st.session_state.setdefault('identified_speakers', [])
    st.session_state.setdefault('speaker_names', {})
    st.session_state.setdefault('summary', '')
    st.session_state.setdefault('error_message', '')
    st.session_state.setdefault('llm_config', {
        'api_url': DEFAULT_LLM_API_URL,
        'api_key': DEFAULT_LLM_API_KEY,
        'model_name': DEFAULT_LLM_MODEL_NAME
    })

init_session_state()

# --- Helper Functions ---
def format_transcription_with_names(transcription: str, mapping: dict) -> str:
    lines = transcription.splitlines()
    out = []
    for L in lines:
        m = re.match(r'^(说话人)\s*(\S+)(.*)', L)
        if m:
            _, sid_full, rest = m.groups()
            speaker_label_in_text = f"说话人 {sid_full}"
            name = mapping.get(speaker_label_in_text, speaker_label_in_text)
            out.append(f"{name}{rest}")
        else:
            out.append(L)
    return '\n'.join(out)


def generate_summary_prompt(info: dict, formatted_transcription: str) -> str:
    topic = info['topic'] or '未指定主题'
    date_str = info['date'].strftime('%Y年%m月%d日')
    time_s = info['time'].strftime('%H:%M')
    loc = info['location'] or '未指定地点'
    example_date_1 = (datetime.date.today() + datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    example_date_2 = (datetime.date.today() + datetime.timedelta(days=15)).strftime('%Y-%m-%d')

    return f"""
下面是一段会议录音的转写文本（已按发言人分离，但可能存在少量错译和说话者识别误差）。请你根据以下要求，生成一份高质量的会议纪要（Markdown格式）：

1. **自动校正**：修正明显的错别字、口语冗余和翻译失误。
2. **说话者融合**：如果发现同一内容被拆分，应合并；说话者标识不准确时，请根据上下文合并或统一标记为“某某（未知）”。
3. **结构清晰**：
   - 标题层级：`# 会议纪要`、`## 基本信息`、`## 主要讨论内容`、`## 会议决议/结论`、`## 行动项`
   - 要点使用无序列表 `-` 或有序列表 `1.`
   - 关键术语、决策或数据用**加粗**突出
4. **详细度**：
   - “主要讨论内容”中，列出 3–5 个议题，每个议题下简要总结讨论要点（2–3 行）。
   - “会议决议/结论”中，明确达成的结论或决定。
   - “行动项”中，为每条行动添加负责人与**建议**的完成期限格式：`- [负责人姓名] — 在 YYYY-MM-DD 前完成：任务描述`。 如果原文中未提及具体负责人或日期，请留空或写“待定”。

**会议基本信息**
- 主题：{topic}
- 时间：{date_str} {time_s}
- 地点：{loc}

**会议内容（转写文本）：**
{formatted_transcription}

---
请基于以上信息生成会议纪要：
# 会议纪要
## 基本信息
- **主题**: {topic}
- **时间**: {date_str} {time_s}
- **地点**: {loc}
- **参会人员**: (如果转写文本中能识别，请列出；否则留空或写“未记录”)

## 主要讨论内容
(请根据会议内容填写，每个议题后附上主要发言人的讨论摘要)
1. **议题一**：...
   - [发言人A]: ...
   - [发言人B]: ...
2. **议题二**：...
3. **议题三**：...

## 会议决议/结论
(请根据会议内容明确总结)
- ...
- ...

## 行动项
(请按格式填写，如无明确负责人/日期则留空或标注“待定”)
- [张三] — 在 {example_date_1} 前完成：整理会议资料并分发
- [李四] — 在 {example_date_2} 前完成：与供应商确认下一步细节
"""

# --- Streamlit App Layout ---
st.set_page_config(page_title='会议助手', layout='centered')
st.title('🎙️ 会议助手')

# # Sidebar: LLM config (optional, can be re-enabled if needed)
# # 您可以取消注释这部分，如果希望用户可以自定义 LLM 配置
# with st.sidebar:
#     st.header('⚙️ LLM 配置 (可选)')
#     st.caption("默认配置从 `.env` 文件加载。您可以在此处临时修改。")
#     st.session_state.llm_config['api_url'] = st.text_input(
#         'LLM API URL', st.session_state.llm_config['api_url'])
#     st.session_state.llm_config['api_key'] = st.text_input(
#         'LLM API Key', st.session_state.llm_config['api_key'], type='password')
#     st.session_state.llm_config['model_name'] = st.text_input(
#         'LLM 模型名称', st.session_state.llm_config['model_name'])
#     if st.button("保存LLM配置到会话"): # 这个按钮是针对LLM配置的，可以保留
#         st.success("LLM配置已更新至当前会话。")


# Step 1: Meeting info & upload
st.header('步骤1: 录音上传 & 会议信息')
mi = st.session_state.meeting_info
col1, col2 = st.columns(2)
with col1:
    mi['date'] = st.date_input('会议日期', mi['date'])
with col2:
    mi['time'] = st.time_input('会议时间', mi['time'])
mi['topic'] = st.text_input('会议主题', mi['topic'])
mi['location'] = st.text_input('会议地点', mi['location'])

upload = st.file_uploader('上传录音 (wav, mp3, m4a, ogg, flac)', type=['wav','mp3','m4a','ogg','flac'])
if upload is not None:
    if upload != st.session_state.uploaded_audio: # New file uploaded
        st.session_state.uploaded_audio = upload
        st.session_state.task_id = None
        st.session_state.task_status = 'idle'
        st.session_state.raw_transcription = ''
        st.session_state.editable_transcription = ''
        st.session_state.identified_speakers = []
        st.session_state.speaker_names = {}
        st.session_state.summary = ''
        st.session_state.error_message = ''
        st.success(f'已选文件: {upload.name}')
elif st.session_state.uploaded_audio is not None:
    st.success(f'当前文件: {st.session_state.uploaded_audio.name}')


# Step 2: Transcription submission & polling
if st.button('🚀 开始转录', disabled=(st.session_state.uploaded_audio is None or st.session_state.task_status == 'processing')):
    if st.session_state.uploaded_audio:
        # 重置状态以防重复点击或新文件上传后的旧状态残留
        st.session_state.task_id = None
        st.session_state.raw_transcription = ''
        st.session_state.editable_transcription = ''
        st.session_state.identified_speakers = []
        st.session_state.speaker_names = {}
        st.session_state.summary = ''
        st.session_state.error_message = ''

        files = {'file': (st.session_state.uploaded_audio.name, st.session_state.uploaded_audio.getvalue(), st.session_state.uploaded_audio.type)}
        try:
            st.session_state.task_status = 'submitting'
            st.info('正在提交转录任务...')
            resp = requests.post(f"http://{BACKEND_API_URL}:{APP_PORT_BACKEND}/api/transcribe", files=files, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            st.session_state.task_id = data.get('task_id')
            st.session_state.task_status = 'processing' # 更新状态以触发轮询逻辑
            st.session_state.error_message = ''
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.session_state.error_message = f'提交转录任务失败: {e}'
            st.session_state.task_status = 'failed'
            st.error(st.session_state.error_message) # 在按钮下方显示错误
        except Exception as e:
            st.session_state.error_message = f'发生意外错误: {e}'
            st.session_state.task_status = 'failed'
            st.error(st.session_state.error_message) # 在按钮下方显示错误


if st.session_state.task_status == 'processing' and st.session_state.task_id:
    status_message_placeholder = st.empty()
    progress_bar_placeholder = st.empty()

    with st.spinner('转录进行中，请耐心等待...'): # Spinner 会覆盖 placeholder
        start_time = time.time()
        POLLING_INTERVAL = 5
        MAX_POLLING_TIME = 600

        while True:
            if not st.session_state.task_id:
                st.session_state.task_status = 'failed'
                st.session_state.error_message = "任务ID丢失，无法查询状态。"
                status_message_placeholder.error(st.session_state.error_message)
                break
            try:
                resp = requests.get(f"http://{BACKEND_API_URL}:{APP_PORT_BACKEND}/api/job/{st.session_state.task_id}", timeout=10)
                resp.raise_for_status()
                job = resp.json()
            except requests.exceptions.RequestException as e:
                if time.time() - start_time > MAX_POLLING_TIME / 2 : # Avoid infinite loop on persistent error
                    st.session_state.error_message = f'查询状态时网络错误: {e}. 后端服务可能不可用。'
                    st.session_state.task_status = 'failed'
                    status_message_placeholder.error(st.session_state.error_message)
                    break
                status_message_placeholder.warning(f"查询状态时遇到临时网络问题，将重试... ({e})")
                time.sleep(POLLING_INTERVAL * 2)
                continue

            backend_status = job.get('status', 'UNKNOWN').upper()
            status_message_placeholder.info(f'后端任务状态: {backend_status}')

            elapsed_time = time.time() - start_time
            progress_value = min(int((elapsed_time / (MAX_POLLING_TIME * 0.9)) * 100), 99) # Simulate progress

            if backend_status not in ['COMPLETED', 'FAILED']:
                progress_bar_placeholder.progress(progress_value)
            
            if backend_status == 'COMPLETED':
                progress_bar_placeholder.progress(100)
                status_message_placeholder.success('转录完成!')
                raw_transcription = job.get('transcription', '').strip()
                st.session_state.raw_transcription = raw_transcription # 保存原始转录
                st.session_state.editable_transcription = raw_transcription # 初始化可编辑转录

                spk_matches = re.findall(r'(说话人\s*[^\[]+)\s*\[', raw_transcription)
                unique_speakers = sorted(list(set(spk.strip() for spk in spk_matches)))
                st.session_state.identified_speakers = unique_speakers
                
                # 保留已有的发言人姓名映射，同时为新识别的发言人添加空映射
                updated_speaker_names = st.session_state.speaker_names.copy()
                for spk_id_label in unique_speakers:
                    if spk_id_label not in updated_speaker_names:
                        updated_speaker_names[spk_id_label] = '' # 或 spk_id_label 作为默认名
                st.session_state.speaker_names = updated_speaker_names

                st.session_state.task_status = 'completed'
                st.session_state.error_message = ''
                # 清理占位符并rerun以刷新UI到下一步
                time.sleep(1) # 短暂显示成功信息
                status_message_placeholder.empty()
                progress_bar_placeholder.empty()
                st.rerun()
                break

            elif backend_status == 'FAILED':
                progress_bar_placeholder.empty()
                error_detail = job.get('error', '未知转录错误')
                st.session_state.error_message = f'转录失败: {error_detail}'
                st.session_state.task_status = 'failed'
                status_message_placeholder.error(st.session_state.error_message) # Display error
                break

            if time.time() - start_time > MAX_POLLING_TIME:
                progress_bar_placeholder.empty()
                st.session_state.error_message = '转录超时，请检查后端服务或稍后重试。'
                st.session_state.task_status = 'failed'
                status_message_placeholder.warning(st.session_state.error_message) # Display warning
                break
            time.sleep(POLLING_INTERVAL)

# 在轮询结束后，如果状态不是 processing 或 submitting，则清空消息占位符
if st.session_state.task_status not in ['processing', 'submitting']:
    if 'status_message_placeholder' in locals() and hasattr(status_message_placeholder, 'empty'):
        status_message_placeholder.empty()
    if 'progress_bar_placeholder' in locals() and hasattr(progress_bar_placeholder, 'empty'):
        progress_bar_placeholder.empty()


# Step 3: Edit transcription & speaker mapping (显示在转录完成后)
if st.session_state.task_status == 'completed' and st.session_state.raw_transcription: # 确保有转录文本
    st.header('步骤2: 编辑转录 & 修正发言人')
    
    st.caption("您可以在下方的文本编辑器中编辑自动转录的结果，修正识别错误。编辑器支持行号（在左侧边栏显示）、查找替换等功能。")

    current_transcription_for_editor = st.session_state.get('editable_transcription', '')

    edited_content = st_ace(
        value=current_transcription_for_editor,
        key="ace_editor",
        language="text",
        theme="chrome", 
        height=400,
        font_size=14,
        wrap=True,
        show_gutter=True,       # <--- 修改: 控制左侧边栏（通常包含行号）的显示
        auto_update=True,
        readonly=False
        # placeholder="请在此编辑您的转录文本..." # <--- 移除: placeholder 可能不是 st_ace 的标准参数
        # show_line_numbers=True, # <--- 移除: 这个参数导致了错误
    )

    if edited_content != current_transcription_for_editor:
        st.session_state.editable_transcription = edited_content

    # --- 修正发言人姓名的代码保持不变 ---
    if st.session_state.identified_speakers:
        st.markdown('#### 修正发言人姓名：')
        st.caption("将识别出的“说话人 X”映射为您期望的真实姓名。")
        
        num_speakers = len(st.session_state.identified_speakers)
        cols_per_row = min(num_speakers, 3) 

        for i in range(0, num_speakers, cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < num_speakers:
                    speaker_id_label = st.session_state.identified_speakers[i+j]
                    input_key = f'speaker_name_input_for_{speaker_id_label.replace(" ", "_").replace("[","").replace("]","")}'
                    current_name_for_input = st.session_state.speaker_names.get(speaker_id_label, '')
                    
                    user_entered_name = cols[j].text_input(
                        f'{speaker_id_label} →',
                        value=current_name_for_input,
                        key=input_key,
                        placeholder="输入姓名"
                    )
                    if st.session_state.speaker_names.get(speaker_id_label) != user_entered_name:
                        st.session_state.speaker_names[speaker_id_label] = user_entered_name


# Step 4: Generate summary (显示在转录完成后)
if st.session_state.task_status == 'completed':
    st.header('步骤3: 生成会议纪要')
    if st.button('✨ 生成会议纪要', disabled=(not st.session_state.editable_transcription)):
        with st.spinner('正在连接大模型生成会议纪要...'):
            try:
                formatted_transcription_for_summary = format_transcription_with_names(
                    st.session_state.editable_transcription, 
                    st.session_state.speaker_names
                )
                prompt = generate_summary_prompt(st.session_state.meeting_info, formatted_transcription_for_summary)

                headers = {
                    'Authorization': f"Bearer {st.session_state.llm_config['api_key']}",
                    'Content-Type': 'application/json'
                }
                payload = {
                    'model': st.session_state.llm_config['model_name'],
                    'messages': [{'role': 'user', 'content': prompt}],
                }

                llm_api_url = st.session_state.llm_config['api_url']
                if not llm_api_url:
                    st.session_state.error_message = "LLM API URL 未配置，无法生成纪要。"
                    st.error(st.session_state.error_message) # 在按钮下方显示错误
                else:
                    res = requests.post(llm_api_url, headers=headers, json=payload, timeout=180)
                    res.raise_for_status()
                    response_data = res.json()

                    if 'choices' in response_data and response_data['choices']:
                        content = response_data['choices'][0].get('message', {}).get('content', '')
                        content = content.split("</think>\n")[-1] if "</think>" in content else content
                        content = re.sub(r'^```markdown\s*', '', content, flags=re.IGNORECASE)
                        content = re.sub(r'\s*```$', '', content, flags=re.IGNORECASE)
                        st.session_state.summary = content.strip()
                        st.session_state.error_message = ''
                        st.success('✅ 会议纪要生成成功!')
                    else:
                        st.session_state.error_message = f"LLM响应格式不正确或无内容: {response_data.get('error', response_data)}"
                        st.error(st.session_state.error_message) # 在按钮下方显示错误

            except requests.exceptions.HTTPError as http_err:
                err_content = "N/A"
                try:
                    err_content = http_err.response.json()
                except ValueError:
                    err_content = http_err.response.text
                st.session_state.error_message = f"LLM API 请求失败 (HTTP {http_err.response.status_code}): {err_content}"
                st.error(st.session_state.error_message)
            except requests.exceptions.RequestException as req_err:
                st.session_state.error_message = f"连接 LLM API 时发生网络错误: {req_err}"
                st.error(st.session_state.error_message)
            except Exception as e:
                st.session_state.error_message = f"生成会议纪要时发生未知错误: {e}"
                st.error(st.session_state.error_message)


# Display summary
if st.session_state.summary:
    st.header('📝 会议纪要预览')
    st.markdown(st.session_state.summary, help="这是生成的会议纪要内容。")
    topic_for_filename = re.sub(r'[^\w\s-]', '', st.session_state.meeting_info.get('topic','未命名会议')).strip().replace(' ', '_')
    date_for_filename = st.session_state.meeting_info.get('date',datetime.date.today()).strftime('%Y%m%d')
    download_filename = f"会议纪要_{topic_for_filename}_{date_for_filename}.md"
    
    st.download_button(
        label="📥 下载会议纪要 (Markdown)",
        data=st.session_state.summary,
        file_name=download_filename,
        mime="text/markdown",
    )

# Display any persistent error messages at the bottom if not already shown by specific sections
if st.session_state.error_message and st.session_state.task_status not in ['processing', 'submitting']:
    # st.error(f"提示: {st.session_state.error_message}") # 可根据需要决定是否保留此通用错误显示
    pass