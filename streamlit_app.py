import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import threading
import json

# --- Global WebSocket variable to avoid Streamlit threading issues ---
websocket = None

# --- Constants ---
RATE = 16000
URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
API_KEY = st.secrets["general"]["ASSEMBLYAI_API_KEY"]

# --- Setup Session State ---
if "run" not in st.session_state:
    st.session_state.run = False
if "text" not in st.session_state:
    st.session_state.text = "Press Start to begin."
if "transcription_result" not in st.session_state:
    st.session_state.transcription_result = ""
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None

# --- UI ---
st.set_page_config(page_title="Real-Time Transcription", layout="centered")
st.title("🎙️ Real-Time Transcription with AssemblyAI")

col1, col2 = st.columns(2)
if col1.button("Start"):
    st.session_state.run = True
    st.session_state.text = "Connecting..."
    st.session_state.transcription_result = ""
    st.write("▶️ Start button clicked")
    st.write(f"📌 run state: {st.session_state.run}")

if col2.button("Stop"):
    st.session_state.run = False
    st.session_state.text = "Stopped"
    st.write("⏹️ Stop button clicked")

st.info(st.session_state.text)

if st.session_state.transcription_result:
    st.download_button(
        label="Download Transcription",
        data=st.session_state.transcription_result,
        file_name="transcription.txt",
        mime="text/plain"
    )

# --- Async WebSocket receiver function ---
async def receiver():
    global websocket
    headers = {"Authorization": API_KEY}
    print("🌐 Attempting WebSocket connection...")

    try:
        async with websockets.connect(URL, extra_headers=headers) as ws:
            print("✅ Connected to WebSocket")
            websocket = ws

            while st.session_state.run:
                try:
                    msg = await ws.recv()
                    print(f"📥 Received message: {msg[:80]}...")
                    data = json.loads(msg)

                    # Update st.session_state safely here in main thread
                    if data["message_type"] == "PartialTranscript":
                        st.session_state.text = f"Partial: {data['text']}"
                    elif data["message_type"] == "FinalTranscript":
                        st.session_state.transcription_result += data["text"] + "\n"
                        st.session_state.text = f"Final: {data['text']}"
                except Exception as e:
                    print("❌ WebSocket receive error:", e)
                    break
    except Exception as e:
        print("❌ WebSocket connection error:", e)

# --- Function to start the receiver in a separate thread ---
def start_ws_thread():
    def run_loop():
        print("🧵 Starting asyncio event loop in thread")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(receiver())
        except Exception as e:
            print("❌ Exception in thread:", e)
        finally:
            loop.close()
            print("🛑 Event loop closed")

    if st.session_state.ws_thread is None:
        print("🚀 Launching WebSocket thread...")
        st.session_state.ws_thread = threading.Thread(target=run_loop, daemon=True)
        st.session_state.ws_thread.start()
    else:
        print("🟢 WebSocket thread already running")

# --- Audio Processor ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        global websocket
        if st.session_state.run and websocket:
            try:
                audio_bytes = frame.to_ndarray().tobytes()
                asyncio.run_coroutine_threadsafe(
                    websocket.send(audio_bytes),
                    asyncio.get_event_loop()
                )
                print("🔊 Sent audio frame")
            except Exception as e:
                print("❌ Audio send error:", e)
        return frame

# --- WebRTC Streamer ---
webrtc_ctx = webrtc_streamer(
    key="audio-stream",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioSender,
    media_stream_constraints={"video": False, "audio": True},
    audio_html_attrs={"controls": True, "autoPlay": True}
)

# --- Launch WebSocket thread if running ---
if st.session_state.run:
    start_ws_thread()
