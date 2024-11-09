from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import torch
from pathlib import Path

from beavervision.api import router
from beavervision.utils.monitoring import init_monitoring
from beavervision.config import settings
from beavervision.utils.logger import setup_logger

logger = setup_logger(__name__)

# Initialize the FastAPI application
app = FastAPI(
    title="BeaverVision API",
    description="Real-time lip synchronization API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize monitoring
init_monitoring()

# Create and mount static directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the test page."""
    try:
        test_page = static_dir / "test.html"
        if not test_page.exists():
            # Create test.html if it doesn't exist
            test_page.write_text("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BeaverVision Lip Sync Test</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto p-4">
        <h1 class="text-3xl font-bold mb-8">BeaverVision Lip Sync Test</h1>
        
        <!-- Webcam Section -->
        <div class="mb-8">
            <h2 class="text-xl font-semibold mb-4">Webcam Input</h2>
            <video id="webcam" class="w-full max-w-lg border rounded" autoplay playsinline></video>
            <button id="startRecording" class="mt-4 bg-blue-500 text-white px-4 py-2 rounded">Start Recording</button>
            <button id="stopRecording" class="mt-4 bg-red-500 text-white px-4 py-2 rounded hidden">Stop Recording</button>
        </div>

        <!-- Upload Section -->
        <div class="mb-8">
            <h2 class="text-xl font-semibold mb-4">Or Upload Video</h2>
            <input type="file" id="videoUpload" accept="video/*" class="mb-4">
            <video id="uploadPreview" class="w-full max-w-lg border rounded hidden" controls></video>
        </div>

        <!-- Text Input -->
        <div class="mb-8">
            <h2 class="text-xl font-semibold mb-4">Text to Speak</h2>
            <textarea id="textInput" 
                      class="w-full max-w-lg p-2 border rounded" 
                      rows="3"
                      placeholder="Enter the text you want the video to speak..."></textarea>
        </div>

        <!-- Process Button -->
        <button id="processButton" 
                class="bg-green-500 text-white px-6 py-3 rounded text-lg disabled:bg-gray-400"
                disabled>
            Process Video
        </button>

        <!-- Result Section -->
        <div id="resultSection" class="mt-8 hidden">
            <h2 class="text-xl font-semibold mb-4">Result</h2>
            <video id="resultVideo" class="w-full max-w-lg border rounded" controls></video>
            <a id="downloadLink" 
               class="mt-4 inline-block bg-blue-500 text-white px-4 py-2 rounded"
               download="lipsync_result.mp4">
                Download Result
            </a>
        </div>

        <!-- Loading Indicator -->
        <div id="loadingIndicator" class="hidden mt-8">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            <p class="mt-2">Processing... This may take a few moments.</p>
        </div>
    </div>

    <script>
        let mediaRecorder;
        let recordedChunks = [];
        let videoBlob = null;

        // Webcam setup
        async function setupWebcam() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                document.getElementById('webcam').srcObject = stream;
                setupRecording(stream);
            } catch (error) {
                console.error('Error accessing webcam:', error);
                alert('Could not access webcam');
            }
        }

        // Recording setup
        function setupRecording(stream) {
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                videoBlob = new Blob(recordedChunks, { type: 'video/webm' });
                recordedChunks = [];
                document.getElementById('processButton').disabled = false;
            };
        }

        // Event Listeners
        document.getElementById('startRecording').addEventListener('click', () => {
            recordedChunks = [];
            mediaRecorder.start();
            document.getElementById('startRecording').classList.add('hidden');
            document.getElementById('stopRecording').classList.remove('hidden');
        });

        document.getElementById('stopRecording').addEventListener('click', () => {
            mediaRecorder.stop();
            document.getElementById('stopRecording').classList.add('hidden');
            document.getElementById('startRecording').classList.remove('hidden');
        });

        document.getElementById('videoUpload').addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                videoBlob = file;
                const preview = document.getElementById('uploadPreview');
                preview.src = URL.createObjectURL(file);
                preview.classList.remove('hidden');
                document.getElementById('processButton').disabled = false;
            }
        });

        document.getElementById('processButton').addEventListener('click', async () => {
            if (!videoBlob) {
                alert('Please record or upload a video first');
                return;
            }

            const text = document.getElementById('textInput').value.trim();
            if (!text) {
                alert('Please enter some text');
                return;
            }

            const loadingIndicator = document.getElementById('loadingIndicator');
            loadingIndicator.classList.remove('hidden');

            const formData = new FormData();
            formData.append('video', videoBlob);
            formData.append('text', text);

            try {
                const response = await fetch('/api/v1/lipsync', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const resultBlob = await response.blob();
                const resultVideo = document.getElementById('resultVideo');
                const resultUrl = URL.createObjectURL(resultBlob);
                resultVideo.src = resultUrl;
                
                document.getElementById('downloadLink').href = resultUrl;
                document.getElementById('resultSection').classList.remove('hidden');
            } catch (error) {
                console.error('Error:', error);
                alert('Error processing video: ' + error.message);
            } finally {
                loadingIndicator.classList.add('hidden');
            }
        });

        // Initialize webcam on page load
        setupWebcam();
    </script>
</body>
</html>
            """)
        return FileResponse(test_page)
    except Exception as e:
        logger.error(f"Error serving test page: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    }

# Include API router
app.include_router(router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )