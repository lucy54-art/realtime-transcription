import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import asyncio
import base64
import json
import threading
import queue
import time

# -----------------------------
# AssemblyAI websocket realtime API URL with sample_rate 16000
ASSEMBLYAI_WS_URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

# Get your AssemblyAI API key from Streamlit secrets
API_KEY = st.secrets["api_key"]

# -----------------------------
# Session state initialization
if "run" not in st.session_state:
    st.session_state.run = False
if "transcript" not in st.session_state:
    st.session_state.transcript = ""

# -----------------------------
# Queue to send audio chunks from AudioProcessor thread to main asyncio websocket task
audio_queue = queue.Queue()

# -----------------------------
# Audio processor class to get audio frames and put in queue
class AudioProcessor(AudioProcessorBase):
    def recv(self, frame):
        if st.session_state.run:
            # Put raw audio bytes in the queue
            audio_queue.put(frame.to_ndarray().tobytes())
        return frame

# -----------------------------
# Async function to handle websocket send/receive
async def websocket_send_receive():
    import websockets

    async with websockets.connect(
        ASSEMBLYAI_WS_URL,
        extra_headers=(("Authorization", API_KEY),),
        ping_interval=5,
        ping_timeout=20,
    ) as ws:

        # Wait for session begin message
        session_begins = await ws.recv()
        print("Session begin:", session_begins)

        # Coroutine to send audio data
        async def send_audio():
            while st.session_state.run:
                try:
                    audio_chunk = audio_queue.get(timeout=1)
                except queue.Empty:
                    continue
                # Base64 encode audio chunk
                data = base64.b64encode(audio_chunk).decode("utf-8")
                json_data = json.dumps({"audio_data": data})
                await ws.send(json_data)
                await asyncio.sleep(0.01)
            # Send a close frame when done
            await ws.send(json.dumps({"terminate_session": True}))

        # Coroutine to receive transcription results
        async def receive_transcripts():
            while st.session_state.run:
                try:
                    result_str = await ws.recv()
                    result_json = json.loads(result_str)

                    if result_json.get("message_type") == "FinalTranscript":
                        text = result_json.get("text", "")
                        if text:
                            st.session_state.transcript += text + " "
                            # Update UI
                            st.experimental_rerun()
                except Exception as e:
                    print("Receive error:", e)
                    break

        # Run sending and receiving concurrently
        await asyncio.gather(send_audio(), receive_transcripts())

# -----------------------------
# Function to start websocket task in background thread
def start_websocket_loop():
    if not st.session_state.run:
        st.session_state.run = True
        st.session_state.transcript = ""
        # Run asyncio loop in new thread to not block Streamlit
        def runner():
            asyncio.run(websocket_send_receive())
            st.session_state.run = False

        threading.Thread(target=runner, daemon=True).start()

# -----------------------------
# Function to stop listening
def stop_listening():
    st.session_state.run = False

# -----------------------------
# Streamlit UI

st.title("🎙️ Real-Time Transcription with AssemblyAI & streamlit-webrtc")

col1, col2 = st.columns([1,1])
with col1:
    if st.session_state.run:
        st.button("Stop Listening", on_click=stop_listening)
    else:
        st.button("Start Listening", on_click=start_websocket_loop)

with col2:
    st.download_button(
        "Download Transcript",
        st.session_state.transcript,
        file_name="transcription.txt",
        mime="text/plain",
    )

st.markdown("### Transcript 📝")
st.text_area("Transcription output", value=st.session_state.transcript, height=300)

# -----------------------------
# Start the streamlit-webrtc component only when running

if st.session_state.run:
    webrtc_streamer(
        key="assemblyai-websocket",
        mode=WebRtcMode.SENDONLY,
        audio_processor_factory=AudioProcessor,
        media_stream_constraints={"audio": True, "video": False},
        async_processing=True,
    )

