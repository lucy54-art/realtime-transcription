import streamlit as st
import websockets
import asyncio
import base64
import json
import os
from pathlib import Path
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase

# Session state
if 'text' not in st.session_state:
    st.session_state['text'] = 'Listening...'
    st.session_state['run'] = False
if 'transcription_result' not in st.session_state:
    st.session_state['transcription_result'] = ""

# Audio parameters (These might need adjustment or confirmation based on your AssemblyAI requirements)
st.sidebar.header('Audio Parameters')

# FRAMES_PER_BUFFER and FORMAT are less relevant with streamlit-webrtc as it handles the browser audio capture
# CHANNELS = 1 # Already hardcoded in the AssemblyAI URL below
RATE = int(st.sidebar.text_input('Sample Rate', 16000)) # Sample rate for AssemblyAI

# AssemblyAI Real-Time Transcription API endpoint
URL = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}"

# Start/stop flags for the app
def start_listening():
    st.session_state['run'] = True

def stop_listening():
    st.session_state['run'] = False

# Function to download the transcription
def download_transcription():
    st.download_button(
        label="Download transcription",
        data=st.session_state['transcription_result'],
        file_name='transcription_output.txt',
        mime='text/plain')

# Web user interface
st.title('🎙️ Real-Time Transcription App')

with st.expander('About this App'):
    st.markdown('''
    This Streamlit app uses the AssemblyAI API to perform real-time transcription, capturing audio directly from the user's browser.

    Libraries used:
    - `streamlit` - web framework
    - `streamlit-webrtc` - real-time audio/video processing from the browser
    - `websockets` - allows interaction with the API
    - `asyncio` - allows concurrent input/output processing (though less explicitly needed with `streamlit-webrtc`)
    - `base64` - (might still be needed for encoding/decoding if your API requires it)
    - `json` - allows reading of AssemblyAI audio output in JSON format
    ''')

col1, col2 = st.columns(2)

# Use streamlit-webrtc to capture audio from the browser
webrtc_ctx = webrtc_streamer(
    key="realtime_transcription",
    mode=WebRtcMode.SENDONLY,  # We only need to send audio to the server
    audio_html_attrs={"autoPlay": True, "controls": True}, # Optional: Display controls
    # Add this line to request only audio access:
    media_stream_constraints={"video": False, "audio": True} 
)

# Stream processing logic (inside a callback, which `streamlit-webrtc` handles)
# We'll use a class-based approach for the audio processor
class TranscriptionProcessor(AudioProcessorBase):
    def __init__(self, websocket_url):
        self.websocket_url = websocket_url
        self.websocket = None
        self.loop = None
        self.result_container = [] # To store transcription results
        self.st_text_placeholder = st.empty() # Placeholder for displaying text

    def recv(self, frame):
        """
        Receives an audio frame and sends it to the AssemblyAI API via WebSocket.
        """
        if self.websocket and st.session_state['run']:
            # Convert audio frame to bytes and send over WebSocket
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                # AssemblyAI expects raw audio data
                self.loop.run_until_complete(self.websocket.send(frame.to_ndarray().tobytes()))
            except websockets.exceptions.ConnectionClosedOK:
                print("WebSocket connection closed")
            except Exception as e:
                print(f"Error sending audio: {e}")
        return frame # Return the frame for potential playback or further processing

    async def run(self):
        """
        Manages the WebSocket connection and receives transcription updates.
        """
        headers = {
            'Authorization': os.environ.get("ASSEMBLYAI_API_KEY") # Replace with your AssemblyAI API key
        }

        async with websockets.connect(self.websocket_url, extra_headers=headers) as self.websocket:
            async for msg in self.websocket:
                data = json.loads(msg)
                if data['message_type'] == 'PartialTranscript':
                    self.st_text_placeholder.write(f"Partial: {data['text']}")
                elif data['message_type'] == 'FinalTranscript':
                    final_text = data['text']
                    self.result_container.append(final_text)
                    st.session_state['transcription_result'] += final_text + "\n"
                    self.st_text_placeholder.write(f"Final: {final_text}")
                elif data['message_type'] == 'Error':
                    print(f"AssemblyAI Error: {data['error']}")

# Integrate the processor with streamlit-webrtc
if webrtc_ctx.state.playing:
    processor = TranscriptionProcessor(websocket_url=URL)
    webrtc_ctx.audio_processor = processor
    asyncio.run(processor.run())

# Display the final transcription result
if st.session_state['transcription_result']:
    st.subheader("Transcription Result:")
    st.text_area("Transcription", st.session_state['transcription_result'], height=300)

    # Download button for the transcription
    download_transcription()

st.info(st.session_state['text']) # Display listening status
