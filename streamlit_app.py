import streamlit as st
import threading
import asyncio
import websockets
import time

import websockets
st.write(f"websockets version: {websockets.__version__}")

# Globals for WebSocket URL and headers example
WS_URL = "wss://your.websocket.url"
WS_HEADERS = {"Authorization": "Bearer your_token"}

# Function to run asyncio event loop forever in thread
def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Async function to connect and manage WebSocket connection
async def websocket_client(run_flag):
    st.write("🌐 Attempting WebSocket connection...")
    try:
        # websockets.connect doesn't accept extra_headers in all versions.
        # So build headers into `headers` param if needed.
        async with websockets.connect(WS_URL, extra_headers=WS_HEADERS) as websocket:
            st.write("✅ WebSocket connected!")
            while run_flag["running"]:
                # Example: send ping every 5 sec
                await websocket.send("ping")
                response = await websocket.recv()
                st.write(f"Received: {response}")
                await asyncio.sleep(5)
    except Exception as e:
        st.write(f"❌ WebSocket connection error: {e}")
    finally:
        st.write("🛑 WebSocket connection closed")

# Setup Streamlit UI
st.title("Async WebSocket with Streamlit")

if "run_flag" not in st.session_state:
    st.session_state.run_flag = {"running": False}
if "loop" not in st.session_state:
    st.session_state.loop = None
if "thread" not in st.session_state:
    st.session_state.thread = None

def start_ws():
    if st.session_state.run_flag["running"]:
        st.write("⚠️ Already running")
        return

    st.session_state.run_flag["running"] = True
    st.write("▶️ Start button clicked")
    st.write(f"📌 run state: {st.session_state.run_flag['running']}")
    st.write("Connecting...")

    # Create new asyncio loop and thread only if not exists or closed
    if st.session_state.loop is None or st.session_state.loop.is_closed():
        loop = asyncio.new_event_loop()
        st.session_state.loop = loop
        thread = threading.Thread(target=start_loop, args=(loop,), daemon=True)
        st.session_state.thread = thread
        thread.start()
        st.write("🚀 Launching WebSocket thread...")

    # Schedule websocket_client in the asyncio loop
    asyncio.run_coroutine_threadsafe(websocket_client(st.session_state.run_flag), st.session_state.loop)

def stop_ws():
    if not st.session_state.run_flag["running"]:
        st.write("⚠️ Not running")
        return
    st.write("🛑 Stop button clicked")
    st.session_state.run_flag["running"] = False

    # Cleanup: stop event loop and thread
    if st.session_state.loop:
        st.session_state.loop.call_soon_threadsafe(st.session_state.loop.stop)
        st.session_state.thread.join(timeout=5)
        st.session_state.loop.close()
        st.write("🧹 Event loop and thread closed")
        st.session_state.loop = None
        st.session_state.thread = None

# Buttons for UI
col1, col2 = st.columns(2)
with col1:
    if st.button("Start"):
        start_ws()
with col2:
    if st.button("Stop"):
        stop_ws()

st.write(f"Current run state: {st.session_state.run_flag['running']}")

