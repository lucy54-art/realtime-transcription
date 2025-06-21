import streamlit as st
import streamlit_webrtc
st.write(streamlit_webrtc.__version__)


# import streamlit as st
# from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings
# import asyncio
# import base64
# import json
# import threading
# import websockets

# # AssemblyAI WebSocket endpoint
# ASSEMBLYAI_WS_URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

# # Your AssemblyAI API key from Streamlit secrets or environment
# API_KEY = st.secrets["api_key"]

# # Global flag to stop streaming
# stop_flag = False

# # Container for transcription results
# transcription_text = ""

# def run_websocket(audio_queue):
#     """Runs in a separate thread: sends audio chunks to AssemblyAI and prints transcription."""
#     global transcription_text
#     async def websocket_handler():
#         async with websockets.connect(
#             ASSEMBLYAI_WS_URL,
#             extra_headers=(("Authorization", API_KEY),),
#             ping_interval=5,
#             ping_timeout=20
#         ) as ws:

#             # Receive session start message
#             session_begins = await ws.recv()
#             print("Session start:", session_begins)

#             async def send_audio():
#                 while not stop_flag:
#                     if not audio_queue.empty():
#                         audio_chunk = audio_queue.get()
#                         if audio_chunk:
#                             # Convert bytes to base64 string
#                             b64_audio = base64.b64encode(audio_chunk).decode("utf-8")
#                             json_data = json.dumps({"audio_data": b64_audio})
#                             await ws.send(json_data)
#                     await asyncio.sleep(0.01)

#             async def receive_transcripts():
#                 global transcription_text
#                 while not stop_flag:
#                     try:
#                         result_str = await ws.recv()
#                         result = json.loads(result_str)
#                         if result.get("message_type") == "FinalTranscript":
#                             text = result.get("text", "")
#                             transcription_text = text
#                             print("Transcription:", text)
#                     except websockets.exceptions.ConnectionClosedOK:
#                         break
#                     except Exception as e:
#                         print("WebSocket receive error:", e)
#                         break

#             await asyncio.gather(send_audio(), receive_transcripts())

#     asyncio.run(websocket_handler())


# def audio_frame_callback(frame):
#     """This callback receives audio frames from the browser."""
#     # frame is an AudioFrame object from streamlit-webrtc
#     # We want raw audio bytes in 16kHz mono, 16bit PCM
#     audio_bytes = frame.to_ndarray(format="int16").tobytes()
#     # Put the audio bytes to the shared queue
#     audio_queue.put(audio_bytes)
#     return frame


# st.title("🎙️ Real-time Transcription with AssemblyAI")

# # Initialize audio queue
# import queue
# audio_queue = queue.Queue()

# # Start the WebRTC streamer
# webrtc_ctx = webrtc_streamer(
#     key="assemblyai",
#     mode=WebRtcMode.SENDONLY,
#     audio_frame_callback=audio_frame_callback,
#     client_settings=ClientSettings(
#         media_stream_constraints={"audio": True, "video": False},
#     ),
#     async_processing=True,
# )

# if st.button("Start Transcription"):
#     stop_flag = False
#     threading.Thread(target=run_websocket, args=(audio_queue,), daemon=True).start()
#     st.success("Started transcription!")

# if st.button("Stop Transcription"):
#     stop_flag = True
#     st.success("Stopped transcription!")

# if transcription_text:
#     st.markdown("### Transcription output:")
#     st.write(transcription_text)
