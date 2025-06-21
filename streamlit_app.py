import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import websockets
import json
import os

# --- App Configuration ---
st.set_page_config(page_title="Real-Time Transcription", layout="centered")

# --- Session State Initialization ---
if "run" not in st.session_state:
    st.session_state.run = False
if "text" not in st.session_state:
    st.session_state.text = "Listening..."
if "transcription_result" not in st.session_state:
    st.session_state.transcription_result = ""
if "websocket" not in st.session_state:
    st.session_state.websocket = None
if "ws_task" not in st.session_state:
    st.session_state.ws_task = None

# --- Constants ---
RATE = 16000
URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"

# --- UI: Title and Controls ---
st.title("🎙️ Real-Time Transcription")

col1, col2 = st.columns(2)
if col1.button("Start"):
    st.session_state.run = True
    st.session_state.text = "Connecting..."
    st.session_state.transcription_result = ""

if col2.button("Stop"):
    st.session_state.run = False
    st.session_state.text = "Stopped"
    if st.session_state.ws_task:
        st.session_state.ws_task.cancel()
        st.session_state.ws_task = None
    st.session_state.websocket = None

# --- Display Status ---
st.info(st.session_state.text)

# --- Download Button for Final Transcript ---
if st.session_state.transcription_result:
    st.download_button(
        label="Download Transcription",
        data=st.session_state.transcription_result,
        file_name="transcription.txt",
        mime="text/plain"
    )

# --- WebSocket Receiver Task ---
async def transcription_receiver():
    headers = {
        "Authorization": st.secrets["ASSEMBLYAI_API_KEY"]
    }

    try:
        async with websockets.connect(URL, extra_headers=headers) as ws:
            st.session_state.websocket = ws
            st.session_state.text = "Connected. Listening..."
            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                if data["message_type"] == "PartialTranscript":
                    st.session_state.text = f"Partial: {data['text']}"
                elif data["message_type"] == "FinalTranscript":
                    final_text = data["text"]
                    st.session_state.text = f"Final: {final_text}"
                    st.session_state.transcription_result += final_text + "\n"
    except asyncio.CancelledError:
        st.session_state.text = "WebSocket task cancelled."
    except Exception as e:
        st.session_state.text = f"WebSocket error: {e}"
        print(f"[WebSocket Error] {e}")

# --- Launch WebSocket Task ---
def ensure_receiver_task():
    if st.session_state.run and st.session_state.ws_task is None:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        st.session_state.ws_task = loop.create_task(transcription_receiver())

# --- Audio Processor Class ---
class AudioSender(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run and st.session_state.websocket:
            try:
                audio_data = frame.to_ndarray().tobytes()
                asyncio.run_coroutine_threadsafe(
                    st.session_state.websocket.send(audio_data),
                    asyncio.get_event_loop()
                )
            except Exception as e:
                print(f"[Audio Send Error] {e}")
        return frame

# --- Start WebRTC Stream ---
webrtc_ctx = webrtc_streamer(
    key="stream",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioSender,
    media_stream_constraints={"video": False, "audio": True},
    audio_html_attrs={"controls": True, "autoPlay": True}
)

# --- Start WebSocket Receiver if Needed ---
if st.session_state.run:
    ensure_receiver_task()

