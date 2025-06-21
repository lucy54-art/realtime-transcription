import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import threading
import json
import os

# --- Session State ---
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

# --- UI ---
st.title("🎙️ Real-Time Transcription")

col1, col2 = st.columns(2)
if col1.button("Start"):
    st.session_state.run = True
    st.session_state.text = "Connecting..."
    st.session_state.transcription_result = ""

if col2.button("Stop"):
    st.session_state.run = False
    st.session_state.text = "Stopped"

    # Close WebSocket if open
    if st.session_state.websocket:
        asyncio.run(close_websocket())
        st.session_state.websocket = None

    # Stop thread
    st.session_state.ws_thread = None

st.info(st.session_state.text)

# --- Download button ---
if st.session_state.transcription_result:
    st.download_button(
        label="Download Transcription",
        data=st.session_state.transcription_result,
        file_name="transcription.txt",
        mime="text/plain"
    )


# --- WebSocket receiver function ---
async def receiver():
    headers = {"Authorization": API_KEY}
    async with websockets.connect(URL, extra_headers=headers) as ws:
        st.session_state.websocket = ws
        st.session_state.text = "Connected. Listening..."
        while st.session_state.run:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                if data["message_type"] == "PartialTranscript":
                    st.session_state.text = f"Partial: {data['text']}"
                elif data["message_type"] == "FinalTranscript":
                    st.session_state.transcription_result += data["text"] + "\n"
                    st.session_state.text = f"Final: {data['text']}"
            except Exception as e:
                st.session_state.text = f"Error: {e}"
                break


def start_ws_thread():
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(receiver())
        loop.close()

    # Start thread if not already running
    if st.session_state.ws_thread is None:
        st.session_state.ws_thread = threading.Thread(target=run_loop, daemon=True)
        st.session_state.ws_thread.start()


# --- Close WebSocket safely ---
async def close_websocket():
    try:
        await st.session_state.websocket.close()
    except:
        pass


# --- Audio Processor ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run and st.session_state.websocket:
            try:
                audio_bytes = frame.to_ndarray().tobytes()
                asyncio.run_coroutine_threadsafe(
                    st.session_state.websocket.send(audio_bytes),
                    asyncio.get_event_loop()
                )
            except Exception as e:
                print(f"Audio Send Error: {e}")
        return frame


# --- WebRTC Streamer ---
webrtc_ctx = webrtc_streamer(
    key="stream",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioSender,
    media_stream_constraints={"video": False, "audio": True},
    audio_html_attrs={"controls": True, "autoPlay": True}
)

# --- Start thread if needed ---
if st.session_state.run:
    start_ws_thread()
