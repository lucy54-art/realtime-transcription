import streamlit as st
import websockets
import asyncio
import base64
import json
import pyaudio
from pathlib import Path
import os

# Initialize session state variables
if 'text' not in st.session_state:
    st.session_state['text'] = '📝 Transcript will appear here...'
if 'run' not in st.session_state:
    st.session_state['run'] = False

# Sidebar: Audio parameters
st.sidebar.header('Audio Parameters')
FRAMES_PER_BUFFER = int(st.sidebar.text_input('Frames per buffer', 3200))
RATE = int(st.sidebar.text_input('Rate', 16000))
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Initialize PyAudio and audio stream
p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=FRAMES_PER_BUFFER
)

# Start listening callback
def start_listening():
    st.session_state['run'] = True

# Stop listening callback
def stop_listening():
    st.session_state['run'] = False

# Download transcription callback
def download_transcription():
    if Path('transcription.txt').is_file():
        with open('transcription.txt', 'r') as f:
            st.download_button(
                label="Download transcription",
                data=f,
                file_name='transcription_output.txt',
                mime='text/plain'
            )
        os.remove('transcription.txt')

# UI title and description
st.title('🎙️ Real-Time Transcription App')
with st.expander('About this App'):
    st.markdown('''
    This Streamlit app uses the AssemblyAI API to perform real-time transcription.
    
    Libraries used:
    - `streamlit` - web framework
    - `pyaudio` - audio processing library
    - `websockets` - WebSocket API interaction
    - `asyncio` - concurrency
    - `base64` - audio data encoding
    - `json` - parsing API responses
    ''')

# Buttons in one row: Start (red) and Stop
col1, col2 = st.columns([1,1])
with col1:
    st.button('Start', on_click=start_listening, type='primary', use_container_width=True)
with col2:
    st.button('Stop Listening', on_click=stop_listening, use_container_width=True)

# Display transcript area
st.markdown('### 📝 Transcript')
transcript_area = st.empty()
transcript_area.text(st.session_state['text'] if st.session_state['text'] else "Connecting...")

# Async function to send audio and receive transcription from AssemblyAI WebSocket
async def send_receive():
    URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
    headers = (("Authorization", st.secrets['api_key']),)

    async with websockets.connect(URL, extra_headers=headers, ping_interval=5, ping_timeout=20) as ws:
        await ws.recv()  # session begins message

        async def send():
            while st.session_state['run']:
                try:
                    data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False)
                    encoded = base64.b64encode(data).decode("utf-8")
                    json_data = json.dumps({"audio_data": encoded})
                    await ws.send(json_data)
                    await asyncio.sleep(0.01)
                except Exception as e:
                    print(f"Send error: {e}")
                    break

        async def receive():
            while st.session_state['run']:
                try:
                    result_str = await ws.recv()
                    result = json.loads(result_str)
                    if result.get('message_type') == 'FinalTranscript':
                        text = result.get('text', '')
                        st.session_state['text'] = text
                        transcript_area.text(text)
                        # Append to transcription.txt
                        with open('transcription.txt', 'a') as f:
                            f.write(text + ' ')
                except Exception as e:
                    print(f"Receive error: {e}")
                    break

        await asyncio.gather(send(), receive())

# Run send_receive if running
if st.session_state['run']:
    asyncio.run(send_receive())

# Show download button if transcription file exists
download_transcription()
