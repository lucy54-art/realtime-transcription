import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import threading
import base64
import json
import queue

# --- Settings & State ---
RATE = 16000
WS_URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
API_KEY = st.secrets["api_key"]

if "run" not in st.session_state:
    st.session_state.run = False
if "text" not in st.session_state:
    st.session_state.text = "Press Start to begin."
if "transcription_result" not in st.session_state:
    st.session_state.transcription_result = ""

# Queue for audio frames and holder for WebSocket
audio_queue = queue.Queue()
websocket_ref = {"ws": None}

# --- WebSocket and Audio Worker ---
def audio_ws_worker():
    async def ws_loop():
        async with websockets.connect(
            WS_URL,
            extra_headers=(("Authorization", API_KEY),),
            ping_interval=5,
            ping_timeout=20
        ) as ws:
            websocket_ref["ws"] = ws
            await ws.recv()  # consume session-start message

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
        b64 = base64.b64encode(chunk).decode("utf-8")
        await ws.send(json.dumps({"audio_data": b64}))
        await asyncio.sleep(0.01)

async def receive_loop(ws):
    while st.session_state.run:
        msg = await ws.recv()
        data = json.loads(msg)
        if data.get("message_type") == "FinalTranscript":
            st.session_state.text = f"Final: {data['text']}"
            st.session_state.transcription_result += data["text"] + "\n"

def start_audio_ws():
    if st.session_state.run and websocket_ref["ws"] is None:
        threading.Thread(target=audio_ws_worker, daemon=True).start()

# --- Audio Frame Processor ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run
