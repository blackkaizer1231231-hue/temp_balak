
import os
import time
import secrets
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


clipboard = {}
lock = asyncio.Lock()
EXPIRY = 86400


@asynccontextmanager
async def lifespan(app):
    async def cleanup():
        while True:
            await asyncio.sleep(300)
            async with lock:
                now = time.time()
                for key in list(clipboard):
                    if now - clipboard[key]["time"] > EXPIRY:
                        del clipboard[key]

    task = asyncio.create_task(cleanup())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


class CopyData(BaseModel):
    text: str


class PasteData(BaseModel):
    key: str


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Universal Clipboard</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    min-height: 100vh;
    background: #090d18;
    color: #f1f5f9;
    font-family: Arial, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}

.container {
    width: 100%;
    max-width: 480px;
}

.brand {
    text-align: center;
    margin-bottom: 30px;
}

.logo {
    font-size: 35px;
    margin-bottom: 10px;
}

h1 {
    font-size: 28px;
    margin: 0 0 10px;
}

.subtitle {
    color: #94a3b8;
    font-size: 14px;
}

.card {
    background: #141b2b;
    border: 1px solid #263248;
    border-radius: 18px;
    padding: 24px;
    margin-bottom: 18px;
}

h2 {
    font-size: 17px;
    margin: 0 0 18px;
}

textarea, input {
    width: 100%;
    background: #0c1322;
    border: 1px solid #344258;
    color: white;
    border-radius: 10px;
    padding: 14px;
    font-size: 15px;
    outline: none;
}

textarea {
    resize: vertical;
    min-height: 125px;
    font-family: inherit;
}

textarea:focus, input:focus {
    border-color: #818cf8;
}

button {
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 10px;
    background: #6366f1;
    color: white;
    font-weight: bold;
    font-size: 15px;
    cursor: pointer;
    margin-top: 14px;
}

button:hover {
    background: #4f46e5;
}

button:disabled {
    opacity: .6;
    cursor: wait;
}

.key-box {
    display: none;
    background: #0c1322;
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    margin-top: 18px;
}

.key {
    font-size: 36px;
    letter-spacing: 8px;
    font-weight: bold;
    color: #a5b4fc;
    margin: 12px 0;
}

.message {
    font-size: 13px;
    color: #94a3b8;
    margin-top: 14px;
    text-align: center;
    overflow-wrap: anywhere;
}

.success {
    color: #4ade80;
}

.error {
    color: #fb7185;
}

.result {
    display: none;
    margin-top: 18px;
}

.result textarea {
    min-height: 140px;
}

.footer {
    text-align: center;
    font-size: 12px;
    color: #64748b;
    margin-top: 25px;
}
</style>
</head>

<body>
<div class="container">

    <div class="brand">
        <div class="logo">📋</div>
        <h1>Universal Clipboard</h1>
        <div class="subtitle">
            Transfer text between any of your devices
        </div>
    </div>

    <div class="card">
        <h2>↑ Send clipboard</h2>

        <textarea id="copyText"
            placeholder="Paste or type your text here..."></textarea>

        <button id="sendBtn" onclick="sendText()">
            Generate 6-Digit Key
        </button>

        <div class="key-box" id="keyBox">
            <div class="subtitle">Your one-time access key</div>
            <div class="key" id="generatedKey"></div>
            <button onclick="copyKey()">Copy Key</button>
            <div class="message success">
                Share this key with your other device.
            </div>
        </div>

        <div class="message" id="sendMessage"></div>
    </div>

    <div class="card">
        <h2>↓ Receive clipboard</h2>

        <input id="pasteKey"
            type="text"
            inputmode="numeric"
            maxlength="6"
            placeholder="Enter 6-digit key">

        <button id="receiveBtn" onclick="receiveText()">
            Retrieve Text
        </button>

        <div class="result" id="result">
            <textarea id="receivedText" readonly></textarea>
            <button onclick="copyReceived()">
                Copy to Clipboard
            </button>
        </div>

        <div class="message" id="receiveMessage"></div>
    </div>

    <div class="footer">
        One-time retrieval · Keys expire after 24 hours
    </div>

</div>

<script>
async function sendText() {
    const text = document.getElementById("copyText").value;
    const btn = document.getElementById("sendBtn");
    const msg = document.getElementById("sendMessage");

    if (!text) {
        msg.textContent = "Please enter some text.";
        msg.className = "message error";
        return;
    }

    btn.disabled = true;
    btn.textContent = "Generating...";
    msg.textContent = "";
    document.getElementById("keyBox").style.display = "none";

    try {
        const response = await fetch("/copy", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text})
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.detail);

        document.getElementById("generatedKey").textContent = data.key;
        document.getElementById("keyBox").style.display = "block";

    } catch (error) {
        msg.textContent = error.message || "Something went wrong.";
        msg.className = "message error";
    } finally {
        btn.disabled = false;
        btn.textContent = "Generate 6-Digit Key";
    }
}

async function receiveText() {
    const key = document.getElementById("pasteKey").value.trim();
    const btn = document.getElementById("receiveBtn");
    const msg = document.getElementById("receiveMessage");
    const result = document.getElementById("result");

    if (!/^\\d{6}$/.test(key)) {
        msg.textContent = "Enter a valid 6-digit key.";
        msg.className = "message error";
        return;
    }

    btn.disabled = true;
    btn.textContent = "Retrieving...";
    result.style.display = "none";

    try {
        const response = await fetch("/paste", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({key})
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.detail);

        document.getElementById("receivedText").value = data.text;
        result.style.display = "block";

        msg.textContent = "Retrieved successfully. This key has been consumed.";
        msg.className = "message success";

    } catch (error) {
        msg.textContent = error.message || "Retrieval failed.";
        msg.className = "message error";
    } finally {
        btn.disabled = false;
        btn.textContent = "Retrieve Text";
    }
}

async function copyKey() {
    await navigator.clipboard.writeText(
        document.getElementById("generatedKey").textContent
    );
}

async function copyReceived() {
    const text = document.getElementById("receivedText").value;
    await navigator.clipboard.writeText(text);

    const msg = document.getElementById("receiveMessage");
    msg.textContent = "Text copied to your clipboard!";
    msg.className = "message success";
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML


@app.post("/copy")
async def copy(data: CopyData):
    async with lock:
        for _ in range(100):
            key = f"{secrets.randbelow(900000) + 100000}"
            if key not in clipboard:
                clipboard[key] = {
                    "text": data.text,
                    "time": time.time()
                }
                return {"key": key}

    raise HTTPException(503, "Could not generate a key")


@app.post("/paste")
async def paste(data: PasteData):
    if not data.key.isdigit() or len(data.key) != 6:
        raise HTTPException(400, "Invalid key")

    async with lock:
        item = clipboard.get(data.key)

        if not item:
            raise HTTPException(404, "Key invalid or already used")

        if time.time() - item["time"] > EXPIRY:
            del clipboard[data.key]
            raise HTTPException(404, "Key expired")

        del clipboard[data.key]

        return {"text": item["text"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )

