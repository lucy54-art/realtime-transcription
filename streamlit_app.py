import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import asyncio
import base64
import json
import websockets

# === Set up session state ===
if 'text' not in st.session_state:
    st.session_state['text'] = ""
if 'run' not in st.session_state:
    st.session_state['run'] = False

# AssemblyAI WebSocket URL, replace with your API key in Streamlit secrets
RATE = 16000
AUDIO_CHUNK_SIZE = 1024  # frames per buffer sent per message

URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"

# Start/Stop buttons
col1, col2 = st.columns(2)

def start_listening():
    st.session_state['run'] = True

def stop_listening():
    st.session_state['run'] = False

col1.button("Start Listening", on_click=start_listening)
col2.button("Stop Listening", on_click=stop_listening)

# Display transcript area
st.markdown("### 📝 Transcript")
transcript_placeholder = st.empty()
transcript_placeholder.write(st.session_state['text'] or "Connecting...")

# Async function to send audio and receive transcription
async def send_receive(ws, audio_queue):
    try:
        # Wait for session begin message
        session_begins = await ws.recv()
        print("Session started:", session_begins)
        
        while st.session_state['run']:
            if audio_queue:
                audio_chunk = audio_queue.pop(0)  # get one audio chunk
                # base64 encode the chunk
                data_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                message = json.dumps({"audio_data": data_b64})
                await ws.send(message)

            try:
                response = await asyncio.wait_for(ws.recv(), timeout=1)
                res_json = json.loads(response)
                if res_json.get("message_type") == "FinalTranscript":
                    text = res_json.get("text", "")
                    if text:
                        st.session_state['text'] += text + " "
                        transcript_placeholder.write(st.session_state['text'])
            except asyncio.TimeoutError:
                pass
        await ws.close()
    except Exception as e:
        print("WebSocket error:", e)

# WebRTC audio processing callback
def audio_frame_callback(frame):
    # Returns raw audio bytes
    return frame.to_ndarray(format="pcm16")

# Run the webrtc streamer in async mode
webrtc_ctx = webrtc_streamer(
    key="assemblyai-websocket",
    mode=WebRtcMode.SENDONLY,
    audio_frame_callback=audio_frame_callback,
    media_stream_constraints={"audio": True, "video": False},
    async_processing=True,
    key_events_enabled=False,
)

# Audio chunk queue
audio_chunks = []

if webrtc_ctx.audio_receiver:
    audio_frame = webrtc_ctx.audio_receiver.get_frame(timeout=1)
    if audio_frame and st.session_state['run']:
        audio_bytes = audio_frame.to_bytes()
        audio_chunks.append(audio_bytes)

# Main event loop to connect websocket and send/receive audio/transcripts
if st.session_state['run'] and webrtc_ctx.state.playing:
    asyncio.run(send_receive(
        websockets.connect(
            URL,
            extra_headers=(("Authorization", st.secrets["api_key"]),),
            ping_interval=5,
            ping_timeout=20,
        ),
        audio_chunks
    ))
