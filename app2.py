# app2.py (English Version)
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
    st.session_state.setdefault('task_status', 'idle') # idle, submitting, processing, completed, failed
    st.session_state.setdefault('raw_transcription', '')
    st.session_state.setdefault('editable_transcription', '')
    st.session_state.setdefault('identified_speakers', [])
    st.session_state.setdefault('speaker_names', {}) # Maps original ID (e.g., "说话人 0") to user-defined name
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
    # This function expects original speaker IDs like "说话人 0" as keys in mapping
    lines = transcription.splitlines()
    out = []
    for L in lines:
        # Regex matches the Chinese speaker prefix from the backend
        m = re.match(r'^(说话人)\s*(\S+)(.*)', L)
        if m:
            _, sid_full, rest = m.groups()
            speaker_label_in_text = f"说话人 {sid_full}" # This is the key expected in the mapping dictionary
            name = mapping.get(speaker_label_in_text, speaker_label_in_text) # Use mapped name or original ID if no mapping
            out.append(f"{name}{rest}")
        else:
            out.append(L)
    return '\n'.join(out)


def generate_summary_prompt(info: dict, formatted_transcription: str) -> str:
    topic = info['topic'] or 'Untitled Topic'
    # Format date and time for an English audience if necessary, though current format is universal
    date_str = info['date'].strftime('%Y-%m-%d') # Standard international format
    time_s = info['time'].strftime('%H:%M')
    loc = info['location'] or 'Not specified'
    example_date_1 = (datetime.date.today() + datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    example_date_2 = (datetime.date.today() + datetime.timedelta(days=15)).strftime('%Y-%m-%d')

    return f"""
The following is the transcribed text of a meeting recording (separated by speaker, but may contain minor inaccuracies and speaker identification errors). Please generate a high-quality meeting minutes document (Markdown format) according to the following requirements:

1.  **Auto-correction**: Correct obvious typos, colloquial redundancies, and minor grammatical errors.
2.  **Speaker Consolidation**: If the same content appears split under slightly different speaker variations that seem to be the same person, it should be merged. If speaker identification is clearly inaccurate for a segment, please use context to assign it to the correct speaker or mark as "Unknown Speaker" if context is insufficient.
3.  **Clear Structure**:
    - Heading levels: Use `# Meeting Minutes`, `## Basic Information`, `## Main Discussion Points`, `## Resolutions/Conclusions`, `## Action Items`.
    - Use unordered lists (`-`) or ordered lists (`1.`) for key points.
    - Highlight key terms, decisions, or data using **bold**.
4.  **Level of Detail**:
    - In "Main Discussion Points", list 3–5 main topics. For each topic, briefly summarize the key discussion points (2–3 lines).
    - In "Resolutions/Conclusions", clearly state the conclusions, decisions, or agreements reached.
    - In "Action Items", for each action, specify the responsible person and a **suggested** completion deadline in the format: `- [Person's Name] — By YYYY-MM-DD: Task description`. If the original text does not mention a specific person or date, leave it blank, write "To be determined", or infer reasonably if possible.

**Meeting Basic Information**
- Topic: {topic}
- Time: {date_str} {time_s}
- Location: {loc}

**Meeting Content (Transcribed Text):**
{formatted_transcription}

---
Please generate the meeting minutes based on the information above:
# Meeting Minutes

## Basic Information
- **Topic**: {topic}
- **Time**: {date_str} {time_s}
- **Location**: {loc}
- **Attendees**: (If identifiable from the transcript, please list them. Otherwise, leave blank or write "Not recorded")

## Main Discussion Points
(Fill in according to the meeting content. For each topic, provide a summary of discussions, attributing points to speakers where possible.)
1.  **Topic One**: ...
    - [Speaker A's Name or Role]: ...
    - [Speaker B's Name or Role]: ...
2.  **Topic Two**: ...
3.  **Topic Three**: ...

## Resolutions/Conclusions
(Clearly summarize the outcomes based on the meeting content.)
- ...
- ...

## Action Items
(Fill in according to the format. If no clear responsible person/date, use "To be determined" or omit that part.)
- [John Doe] — By {example_date_1}: Compile and distribute meeting materials.
- [Jane Smith] — By {example_date_2}: Confirm next steps with the supplier.
"""

# --- Streamlit App Layout ---
st.set_page_config(page_title='Meeting Assistant', layout='centered')
st.title('🎙️ Meeting Assistant')

# # Sidebar: LLM config (optional, can be re-enabled if needed)
# # If you uncomment this, ensure all strings here are also translated
# with st.sidebar:
#     st.header('⚙️ LLM Configuration (Optional)')
#     st.caption("Default settings are loaded from the .env file. You can temporarily override them here.")
#     st.session_state.llm_config['api_url'] = st.text_input(
#         'LLM API URL', st.session_state.llm_config['api_url'])
#     st.session_state.llm_config['api_key'] = st.text_input(
#         'LLM API Key', st.session_state.llm_config['api_key'], type='password')
#     st.session_state.llm_config['model_name'] = st.text_input(
#         'LLM Model Name', st.session_state.llm_config['model_name'])
#     if st.button("Save LLM Config to Session"):
#         st.success("LLM configuration updated for the current session.")


# Step 1: Meeting info & upload
st.header('Step 1: Upload Recording & Meeting Information')
mi = st.session_state.meeting_info
col1, col2 = st.columns(2)
with col1:
    mi['date'] = st.date_input('Meeting Date', mi['date'])
with col2:
    mi['time'] = st.time_input('Meeting Time', mi['time'])
mi['topic'] = st.text_input('Meeting Topic', mi['topic'])
mi['location'] = st.text_input('Meeting Location', mi['location'])

upload = st.file_uploader('Upload Audio Recording (wav, mp3, m4a, ogg, flac)', type=['wav','mp3','m4a','ogg','flac'])
if upload is not None:
    if upload != st.session_state.uploaded_audio: # New file uploaded
        st.session_state.uploaded_audio = upload
        # Reset relevant states for a new file
        st.session_state.task_id = None
        st.session_state.task_status = 'idle'
        st.session_state.raw_transcription = ''
        st.session_state.editable_transcription = ''
        st.session_state.identified_speakers = []
        st.session_state.speaker_names = {}
        st.session_state.summary = ''
        st.session_state.error_message = ''
        st.success(f'Selected file: {upload.name}')
elif st.session_state.uploaded_audio is not None: # File previously uploaded, show its name
    st.success(f'Current file: {st.session_state.uploaded_audio.name}')


# Step 2: Transcription submission & polling
if st.button('🚀 Start Transcription', disabled=(st.session_state.uploaded_audio is None or st.session_state.task_status == 'processing')):
    if st.session_state.uploaded_audio:
        # Reset states for a new transcription process
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
            st.info('Submitting transcription task...')
            # Construct backend URL
            if not BACKEND_API_URL or not APP_PORT_BACKEND:
                st.session_state.error_message = "Backend API URL or Port not configured in .env file."
                st.session_state.task_status = 'failed'
                st.error(st.session_state.error_message)
            else:
                transcribe_url = f"http://{BACKEND_API_URL.strip('/')}:{APP_PORT_BACKEND}/api/transcribe"
                resp = requests.post(transcribe_url, files=files, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                st.session_state.task_id = data.get('task_id')
                st.session_state.task_status = 'processing'
                st.session_state.error_message = ''
                st.rerun()
        except requests.exceptions.RequestException as e:
            st.session_state.error_message = f'Failed to submit transcription task: {e}'
            st.session_state.task_status = 'failed'
            st.error(st.session_state.error_message)
        except Exception as e:
            st.session_state.error_message = f'An unexpected error occurred: {e}'
            st.session_state.task_status = 'failed'
            st.error(st.session_state.error_message)


if st.session_state.task_status == 'processing' and st.session_state.task_id:
    status_message_placeholder = st.empty()
    progress_bar_placeholder = st.empty()

    with st.spinner('Transcription in progress, please wait...'):
        start_time = time.time()
        POLLING_INTERVAL = 5
        MAX_POLLING_TIME = 600 # 10 minutes

        while True:
            if not st.session_state.task_id:
                st.session_state.task_status = 'failed'
                st.session_state.error_message = "Task ID lost, cannot query status."
                status_message_placeholder.error(st.session_state.error_message)
                break
            
            if not BACKEND_API_URL or not APP_PORT_BACKEND:
                st.session_state.error_message = "Backend API URL or Port not configured for status check."
                st.session_state.task_status = 'failed'
                status_message_placeholder.error(st.session_state.error_message)
                break

            try:
                status_url = f"http://{BACKEND_API_URL.strip('/')}:{APP_PORT_BACKEND}/api/job/{st.session_state.task_id}"
                resp = requests.get(status_url, timeout=10)
                resp.raise_for_status()
                job = resp.json()
            except requests.exceptions.RequestException as e:
                if time.time() - start_time > MAX_POLLING_TIME / 2 :
                    st.session_state.error_message = f'Network error while querying status: {e}. Backend service might be unavailable.'
                    st.session_state.task_status = 'failed'
                    status_message_placeholder.error(st.session_state.error_message)
                    break
                status_message_placeholder.warning(f"Temporary network issue while querying status, retrying... ({e})")
                time.sleep(POLLING_INTERVAL * 2)
                continue

            backend_status = job.get('status', 'UNKNOWN').upper()
            status_message_placeholder.info(f'Backend task status: {backend_status}')

            elapsed_time = time.time() - start_time
            progress_value = min(int((elapsed_time / (MAX_POLLING_TIME * 0.9)) * 100), 99)

            if backend_status not in ['COMPLETED', 'FAILED']:
                progress_bar_placeholder.progress(progress_value)
            
            if backend_status == 'COMPLETED':
                progress_bar_placeholder.progress(100)
                status_message_placeholder.success('Transcription complete!')
                raw_transcription = job.get('transcription', '').strip()
                st.session_state.raw_transcription = raw_transcription
                st.session_state.editable_transcription = raw_transcription

                # Extracts speaker IDs like "说话人 0", "说话人 未知"
                spk_matches = re.findall(r'(说话人\s*[^\[]+)\s*\[', raw_transcription)
                unique_speakers = sorted(list(set(spk.strip() for spk in spk_matches)))
                st.session_state.identified_speakers = unique_speakers
                
                updated_speaker_names = st.session_state.speaker_names.copy()
                for spk_id_label in unique_speakers:
                    if spk_id_label not in updated_speaker_names:
                        updated_speaker_names[spk_id_label] = '' 
                st.session_state.speaker_names = updated_speaker_names

                st.session_state.task_status = 'completed'
                st.session_state.error_message = ''
                time.sleep(1) 
                status_message_placeholder.empty()
                progress_bar_placeholder.empty()
                st.rerun()
                break

            elif backend_status == 'FAILED':
                progress_bar_placeholder.empty()
                error_detail = job.get('error', 'Unknown transcription error')
                st.session_state.error_message = f'Transcription failed: {error_detail}'
                st.session_state.task_status = 'failed'
                status_message_placeholder.error(st.session_state.error_message)
                break

            if time.time() - start_time > MAX_POLLING_TIME:
                progress_bar_placeholder.empty()
                st.session_state.error_message = 'Transcription timed out. Please check the backend service or try again later.'
                st.session_state.task_status = 'failed'
                status_message_placeholder.warning(st.session_state.error_message)
                break
            time.sleep(POLLING_INTERVAL)

if st.session_state.task_status not in ['processing', 'submitting']:
    if 'status_message_placeholder' in locals() and hasattr(status_message_placeholder, 'empty'):
        status_message_placeholder.empty()
    if 'progress_bar_placeholder' in locals() and hasattr(progress_bar_placeholder, 'empty'):
        progress_bar_placeholder.empty()


# Step 3: Edit transcription & speaker mapping
if st.session_state.task_status == 'completed' and st.session_state.raw_transcription:
    st.header('Step 2: Edit Transcription & Correct Speakers') 
    
    st.caption("You can edit the auto-transcribed text in the editor below. It supports line numbers, search/replace, etc.")

    current_transcription_for_editor = st.session_state.get('editable_transcription', '')

    edited_content = st_ace(
        value=current_transcription_for_editor,
        key="ace_editor_en", # Use a different key if app.py and app2.py might share session by mistake
        language="text",
        theme="chrome", 
        height=400,
        font_size=14,
        wrap=True,
        show_gutter=True,
        auto_update=True,
        readonly=False
    )

    if edited_content != current_transcription_for_editor:
        st.session_state.editable_transcription = edited_content

    if st.session_state.identified_speakers:
        st.markdown('#### Correct Speaker Names:')
        st.caption("Map the original speaker IDs (e.g., '说话人 X') to their actual names.")
        
        num_speakers = len(st.session_state.identified_speakers)
        cols_per_row = min(num_speakers, 3) 

        for i in range(0, num_speakers, cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < num_speakers:
                    speaker_id_label = st.session_state.identified_speakers[i+j] # This will be like "说话人 0"
                    input_key = f'speaker_name_input_for_en_{speaker_id_label.replace(" ", "_").replace("[","").replace("]","")}'
                    current_name_for_input = st.session_state.speaker_names.get(speaker_id_label, '')
                    
                    # Display the original Chinese ID to the user for mapping
                    user_entered_name = cols[j].text_input(
                        f'Map "{speaker_id_label}" to:', # Show original ID
                        value=current_name_for_input,
                        key=input_key,
                        placeholder="Enter name"
                    )
                    if st.session_state.speaker_names.get(speaker_id_label) != user_entered_name:
                        st.session_state.speaker_names[speaker_id_label] = user_entered_name


# Step 4: Generate summary
if st.session_state.task_status == 'completed':
    st.header('Step 3: Generate Meeting Minutes')
    if st.button('✨ Generate Meeting Minutes', disabled=(not st.session_state.editable_transcription)):
        with st.spinner('Connecting to the LLM to generate meeting minutes...'):
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
                    st.session_state.error_message = "LLM API URL is not configured. Cannot generate minutes."
                    st.error(st.session_state.error_message)
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
                        st.success('✅ Meeting minutes generated successfully!')
                    else:
                        st.session_state.error_message = f"LLM response format incorrect or no content: {response_data.get('error', response_data)}"
                        st.error(st.session_state.error_message)

            except requests.exceptions.HTTPError as http_err:
                err_content = "N/A"
                try:
                    err_content = http_err.response.json() 
                except ValueError: # If response is not JSON
                    err_content = http_err.response.text
                st.session_state.error_message = f"LLM API request failed (HTTP {http_err.response.status_code}): {err_content}"
                st.error(st.session_state.error_message)
            except requests.exceptions.RequestException as req_err:
                st.session_state.error_message = f"Network error connecting to LLM API: {req_err}"
                st.error(st.session_state.error_message)
            except Exception as e:
                st.session_state.error_message = f"An unknown error occurred while generating minutes: {e}"
                st.error(st.session_state.error_message)


# Display summary
if st.session_state.summary:
    st.header('📝 Meeting Minutes Preview')
    st.markdown(st.session_state.summary, help="This is the generated content of the meeting minutes.")
    
    topic_for_filename = re.sub(r'[^\w\s-]', '', st.session_state.meeting_info.get('topic','Untitled_Meeting')).strip().replace(' ', '_')
    date_for_filename = st.session_state.meeting_info.get('date',datetime.date.today()).strftime('%Y%m%d')
    download_filename = f"MeetingMinutes_{topic_for_filename}_{date_for_filename}.md" # English filename
    
    st.download_button(
        label="📥 Download Meeting Minutes (Markdown)",
        data=st.session_state.summary,
        file_name=download_filename,
        mime="text/markdown",
    )

# Display any persistent error messages at the bottom
if st.session_state.error_message and st.session_state.task_status not in ['processing', 'submitting']:
    # st.error(f"Error: {st.session_state.error_message}") # Decide if a generic error display is needed here
    pass