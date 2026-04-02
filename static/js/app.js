/**
 * BeamtimeHero — Chat client
 */
(function () {
    "use strict";

    // Resolve base path from the page URL (strip trailing slash)
    const BASE = window.location.pathname.replace(/\/+$/, "") || "";

    const messagesEl = document.getElementById("messages");
    const inputEl = document.getElementById("chat-input");
    const sendBtn = document.getElementById("btn-send");
    const resetBtn = document.getElementById("btn-reset");
    const typingEl = document.getElementById("typing-indicator");
    const statusDot = document.getElementById("status-dot");

    let ws = null;
    let sending = false;

    // --- WebSocket ---
    function connectWS() {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${proto}//${window.location.host}${BASE}/ws`;

        ws = new WebSocket(url);

        ws.onopen = function () {
            statusDot.classList.remove("disconnected");
            console.log("WebSocket connected");
        };

        ws.onmessage = function (event) {
            const data = JSON.parse(event.data);
            if (data.type === "staff") {
                addMessage("staff", data.text, data.name);
            } else if (data.type === "assistant") {
                addMessage("assistant", data.text, null, data.images);
            }
        };

        ws.onclose = function () {
            statusDot.classList.add("disconnected");
            console.log("WebSocket closed, reconnecting in 3s...");
            setTimeout(connectWS, 3000);
        };

        ws.onerror = function () {
            ws.close();
        };

        // Heartbeat
        setInterval(function () {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send("ping");
            }
        }, 30000);
    }

    // --- Messages ---
    function addMessage(role, text, label, images) {
        const div = document.createElement("div");
        div.className = "message " + role;

        if (label) {
            const labelEl = document.createElement("div");
            labelEl.className = "label";
            labelEl.textContent = label;
            div.appendChild(labelEl);
        } else if (role === "assistant") {
            const labelEl = document.createElement("div");
            labelEl.className = "label";
            labelEl.textContent = "AI Assistant";
            div.appendChild(labelEl);
        }

        const content = document.createElement("div");
        if (role === "user") {
            content.textContent = text;
        } else {
            content.className = "markdown-content";
            content.innerHTML = marked.parse(text || "");
        }
        div.appendChild(content);

        // Render plot images
        if (images && images.length > 0) {
            images.forEach(function (b64) {
                var img = document.createElement("img");
                img.src = "data:image/png;base64," + b64;
                img.className = "plot-image";
                img.alt = "Plot";
                div.appendChild(img);
            });
        }

        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function addSystemMessage(text) {
        const div = document.createElement("div");
        div.className = "message system";
        div.textContent = text;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function showTyping(show) {
        typingEl.classList.toggle("visible", show);
        if (show) {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
    }

    // --- API ---
    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text || sending) return;

        sending = true;
        sendBtn.disabled = true;
        inputEl.value = "";
        inputEl.style.height = "auto";

        addMessage("user", text);
        showTyping(true);

        try {
            const response = await fetch(`${BASE}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
            });

            const data = await response.json();

            if (response.ok) {
                addMessage("assistant", data.response, null, data.images);
            } else {
                addSystemMessage("Error: " + (data.error || "Unknown error"));
            }
        } catch (err) {
            addSystemMessage("Connection error: " + err.message);
        } finally {
            showTyping(false);
            sending = false;
            sendBtn.disabled = false;
            inputEl.focus();
        }
    }

    async function resetConversation() {
        try {
            await fetch(`${BASE}/api/reset`, { method: "POST" });
            messagesEl.innerHTML = "";
            addSystemMessage("Conversation reset. Ask a new question!");
        } catch (err) {
            addSystemMessage("Failed to reset: " + err.message);
        }
    }

    // --- Events ---
    sendBtn.addEventListener("click", sendMessage);

    resetBtn.addEventListener("click", resetConversation);

    inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    inputEl.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    // --- Init ---
    connectWS();
    addSystemMessage("Welcome to BeamtimeHero! Ask questions about your beamline experiment.");
})();
