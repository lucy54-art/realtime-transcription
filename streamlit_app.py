import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import threading
import base64
import json
import queue

# --- Constants ---
RATE = 16000
WS_URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
API_KEY = st.secrets["api_key"]  # Ensure this key is defined in Streamlit Cloud

# --- Session State ---
if "run" not in st.session_state:
    st.session_state.run = False
if "text" not in st.session_state:
    st.session_state.text = "Press Start to begin"
if "transcription_result" not in st.session_state:
    st.session_state.transcription_result = ""

# --- Audio Frame Queue ---
audio_queue = queue.Queue()
websocket_ref = {"ws": None}  # Holder for websocket connection

# --- WebSocket + Transcription Thread ---
def audio_ws_worker():
    async def ws_loop():
        async with websockets.connect(
            WS_URL,
            extra_headers=(("Authorization", API_KEY),),
            ping_interval=5,
            ping_timeout=20
        ) as ws:
            websocket_ref["ws"] = ws
            await ws.recv()  # session start
            send_task = asyncio.create_task(send_audio_loop(ws))
            recv_task = asyncio.create_task(receive_loop(ws))
            await asyncio.gather(send_task, recv_task)

    asyncio.run(ws_loop())

async def send_audio_loop(ws):
    while st.session_state.run:
        try:
            chunk = audio_queue.get(timeout=1)
        except queue.Empty:
            continue
        b64_data = base64.b64encode(chunk).decode("utf-8")
        await ws.send(json.dumps({"audio_data": b64_data}))
        await asyncio.sleep(0.01)

async def receive_loop(ws):
    while st.session_state.run:
        msg = await ws.recv()
        data = json.loads(msg)
        if data.get("message_type") == "FinalTranscript":
            st.session_state.text = f"Final: {data['text']}"
            st.session_state.transcription_result += data["text"] + "\n"

def start_audio_ws_thread():
    if not st.session_state.run:
        return
    thread = threading.Thread(target=audio_ws_worker, daemon=True)
    thread.start()

# --- Audio Processor ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run and websocket_ref["ws"]:
            chunk = frame.to_ndarray(format="int16").tobytes()
            audio_queue.put(chunk)
        return frame

# --- Streamlit UI ---
st.set_page_config(page_title="Real‑Time Transcription", layout="centered")
st.title("🎙️ AssemblyAI Transcription on Streamlit Cloud")

col1, col2 = st.columns(2)
if col1.button("Start"):
    st.session_state.run = True
    st.session_state.text = "Connecting..."
    st.session_state.transcription_result = ""
    start_audio_ws_thread()

if col2.button("Stop"):
    st.session_state.run = False
    st.session_state.text = "Stopped"

webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioSender,
    media_stream_constraints={"audio": True, "video": False},
)

st.info(st.session_state.text)

if st.session_state.transcription_result:
    st.download_button(
        "Download Transcript",
        data=st.session_state.transcription_result,
        file_name="transcript.txt"
    )
