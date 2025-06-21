import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import threading
import json

# --- Setup Session State ---
if "run" not in st.session_state:
    st.session_state.run = False
if "text" not in st.session_state:
    st.session_state.text = "Listening..."
if "transcription_result" not in st.session_state:
    st.session_state.transcription_result = ""
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None
if "websocket" not in st.session_state:
    st.session_state.websocket = None

# --- Constants ---
RATE = 16000
URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"
API_KEY = st.secrets["general"]["ASSEMBLYAI_API_KEY"]

# --- UI Layout ---
st.set_page_config(page_title="Real-Time Transcription", layout="centered")
st.title("🎙️ Real-Time Transcription with AssemblyAI")

col1, col2 = st.columns(2)

if col1.button("Start"):
    st.session_state.run = True
    st.session_state.text = "Connecting..."
    st.session_state.transcription_result = ""
    st.write("▶️ Start button clicked")
    st.write("📌 run state:", st.session_state.run)

if col2.button("Stop"):
    st.session_state.run = False
    st.session_state.text = "Stopped"
    st.write("⏹️ Stop button clicked")

    if st.session_state.websocket:
        st.write("🔌 Closing WebSocket...")
        asyncio.run(close_websocket())
        st.session_state.websocket = None

    st.session_state.ws_thread = None

st.info(st.session_state.text)

# --- Download Button ---
if st.session_state.transcription_result:
    st.download_button(
        label="Download Transcription",
        data=st.session_state.transcription_result,
        file_name="transcription.txt",
        mime="text/plain"
    )

# --- Async WebSocket Receiver ---
async def receiver():
    headers = {"Authorization": API_KEY}
    st.write("🌐 Attempting to connect to AssemblyAI WebSocket...")

    try:
        async with websockets.connect(URL, extra_headers=headers) as ws:
            st.write("✅ Connected to WebSocket")
            print("✅ WebSocket connected")
            st.session_state.websocket = ws
            st.session_state.text = "Connected. Listening..."

            while st.session_state.run:
                try:
                    msg = await ws.recv()
                    print("📥 Message received")
                    st.write(f"📥 Raw Message: {msg[:100]}...")
                    data = json.loads(msg)

                    if data["message_type"] == "PartialTranscript":
                        st.session_state.text = f"Partial: {data['text']}"
                    elif data["message_type"] == "FinalTranscript":
                        st.session_state.transcription_result += data["text"] + "\n"
                        st.session_state.text = f"Final: {data['text']}"
                except Exception as e:
                    st.session_state.text = f"Receiving Error: {e}"
                    st.write(f"❌ Error receiving: {e}")
                    break
    except Exception as e:
        st.session_state.text = f"WebSocket connection error: {e}"
        st.write(f"❌ WebSocket connection error: {e}")
        print(f"❌ WebSocket connection error: {e}")

# --- Close WebSocket ---
async def close_websocket():
    try:
        await st.session_state.websocket.close()
        print("🔌 WebSocket closed")
    except Exception as e:
        st.write(f"⚠️ Error closing WebSocket: {e}")

# --- WebSocket Thread Launcher ---
def start_ws_thread():
    def run_loop():
        st.write("🧵 Starting asyncio loop in new thread")
        print("🧵 Starting asyncio loop in new thread")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(receiver())
        except Exception as e:
            st.write(f"❌ Exception in thread: {e}")
            print(f"❌ Exception in thread: {e}")
        finally:
            loop.close()
            st.write("🛑 Thread event loop closed")
            print("🛑 Thread event loop closed")

    if st.session_state.ws_thread is None:
        st.write("🚀 Launching WebSocket thread...")
        st.session_state.ws_thread = threading.Thread(target=run_loop, daemon=True)
        st.session_state.ws_thread.start()
    else:
        st.write("🟢 WebSocket thread already running")

# --- Audio Processor Class ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run and st.session_state.websocket:
            try:
                audio_bytes = frame.to_ndarray().tobytes()
                asyncio.run_coroutine_threadsafe(
                    st.session_state.websocket.send(audio_bytes),
                    asyncio.get_event_loop()
                )
                print("🔊 Sent audio frame")
            except Exception as e:
                st.write(f"❌ Audio send error: {e}")
                print(f"❌ Audio send error: {e}")
        return frame

# --- WebRTC Audio Streaming ---
webrtc_ctx = webrtc_streamer(
    key="audio-stream",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioSender,
    media_stream_constraints={"video": False, "audio": True},
    audio_html_attrs={"controls": True, "autoPlay": True}
)

# --- Start WebSocket Thread If Needed ---
if st.session_state.run:
    start_ws_thread()

