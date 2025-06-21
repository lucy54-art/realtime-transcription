import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import threading
import base64
import json
import queue

# --- Config & Setup ---
RATE = 16000
WS_URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
API_KEY = st.secrets["api_key"]

# App state
if "run" not in st.session_state:
    st.session_state.run = False
if "text" not in st.session_state:
    st.session_state.text = "Not running."
if "result" not in st.session_state:
    st.session_state.result = ""

# Audio queue and websocket tracker
audio_queue = queue.Queue()
websocket_ref = {"ws": None}

# --- WebSocket thread ---
def ws_thread():
    async def run():
        async with websockets.connect(
            WS_URL,
            extra_headers=(("Authorization", API_KEY),),
            ping_interval=5,
            ping_timeout=20
        ) as ws:
            websocket_ref["ws"] = ws
            await ws.recv()  # consume welcome message

            send_task = asyncio.create_task(send_audio(ws))
            recv_task = asyncio.create_task(recv_text(ws))
            await asyncio.gather(send_task, recv_task)

    asyncio.run(run())

async def send_audio(ws):
    while st.session_state.run:
        try:
            data = audio_queue.get(timeout=1)
        except queue.Empty:
            continue
        b64 = base64.b64encode(data).decode("utf-8")
        await ws.send(json.dumps({"audio_data": b64}))
        await asyncio.sleep(0.01)

async def recv_text(ws):
    while st.session_state.run:
        try:
            msg = await ws.recv()
            response = json.loads(msg)
            if response.get("message_type") == "FinalTranscript":
                text = response["text"]
                st.session_state.text = text
                st.session_state.result += text + "\n"
        except Exception as e:
            print("Error receiving:", e)

# --- AudioProcessor class ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run and websocket_ref["ws"]:
            chunk = frame.to_ndarray().tobytes()
            audio_queue.put(chunk)
        return frame

# --- Streamlit UI ---
st.title("🎙️ Real-Time Transcription (AssemblyAI)")

if not st.session_state.run:
    if st.button("▶️ Start Listening"):
        st.session_state.run = True
        st.session_state.text = "Connecting..."
        st.session_state.result = ""
        threading.Thread(target=ws_thread, daemon=True).start()
else:
    if st.button("⏹ Stop Listening"):
        st.session_state.run = False
        st.session_state.text = "Stopped"

# Always active — it won't show an internal Start button
webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioSender,
    media_stream_constraints={"audio": True, "video": False},
    rtc_configuration={  # Optional: improves compatibility
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    }
)

st.markdown("### 📝 Transcript")
st.write(st.session_state.text or "Waiting for speech...")

if st.session_state.result:
    st.download_button("💾 Download Transcript", st.session_state.result, "transcript.txt")
