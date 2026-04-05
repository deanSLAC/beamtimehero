/**
 * BeamtimeHero — Chat client
 *
 * Three-panel layout: Sidebar (left) + LLM chat (center) + Staff chat (right)
 */
(function () {
    "use strict";

    // Resolve base path from the page URL (strip trailing slash)
    const BASE = window.location.pathname.replace(/\/+$/, "") || "";

    // LLM chat elements
    const messagesEl = document.getElementById("messages");
    const inputEl = document.getElementById("chat-input");
    const sendBtn = document.getElementById("btn-send");
    const resetBtn = document.getElementById("btn-reset");
    const typingEl = document.getElementById("typing-indicator");
    const statusDot = document.getElementById("status-dot");

    // Staff chat elements
    const staffMessagesEl = document.getElementById("staff-messages");
    const staffInputEl = document.getElementById("staff-input");
    const staffSendBtn = document.getElementById("btn-staff-send");

    // Sidebar elements
    const toolsToggle = document.getElementById("tools-toggle");
    const toolsList = document.getElementById("tools-list");
    const refsToggle = document.getElementById("refs-toggle");
    const refsList = document.getElementById("refs-list");

    // Suggestion elements
    const suggestionsToggle = document.getElementById("suggestions-toggle");
    const suggestionsContent = document.getElementById("suggestions-content");
    const suggestionInput = document.getElementById("suggestion-input");
    const suggestionSendBtn = document.getElementById("btn-suggestion-send");
    const suggestionFeedback = document.getElementById("suggestion-feedback");

    let ws = null;
    let sending = false;
    let staffSending = false;

    // --- Sidebar ---
    function setupToggle(btn, list) {
        btn.addEventListener("click", function () {
            btn.classList.toggle("open");
            list.classList.toggle("collapsed");
        });
    }

    async function loadTools() {
        try {
            const response = await fetch(`${BASE}/api/tools`);
            if (!response.ok) return;
            const data = await response.json();

            data.tools.forEach(function (t) {
                const li = document.createElement("li");
                li.innerHTML =
                    '<span class="tool-name">' + escapeHtml(t.name) + "</span>" +
                    '<span class="tool-desc">' + escapeHtml(t.description) + "</span>";
                toolsList.appendChild(li);
            });

            data.references.forEach(function (r) {
                const li = document.createElement("li");
                li.innerHTML =
                    '<span class="tool-name">' + escapeHtml(r.name) + "</span>" +
                    '<span class="tool-desc">' + escapeHtml(r.description) + "</span>";
                refsList.appendChild(li);
            });
        } catch (err) {
            console.error("Failed to load tools:", err);
        }
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

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
            if (data.type === "staff_message") {
                // Staff message from #users channel → staff pane
                addStaffMessage("staff", data.text, data.name);
            } else if (data.type === "staff_in_llm") {
                // Staff message from #llm thread → AI pane
                addMessage("staff", data.text, data.name);
            } else if (data.type === "user_to_staff") {
                // Echo of our message to staff → staff pane
                addStaffMessage("user", data.text);
            } else if (data.type === "assistant") {
                // LLM response → AI pane
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

    // --- LLM Chat Messages ---
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

    // --- Staff Chat Messages ---
    function addStaffMessage(role, text, label) {
        const div = document.createElement("div");
        div.className = "message " + (role === "staff" ? "staff" : "user");

        if (label) {
            const labelEl = document.createElement("div");
            labelEl.className = "label";
            labelEl.textContent = label;
            div.appendChild(labelEl);
        }

        const content = document.createElement("div");
        content.textContent = text;
        div.appendChild(content);

        staffMessagesEl.appendChild(div);
        staffMessagesEl.scrollTop = staffMessagesEl.scrollHeight;
    }

    function addStaffSystemMessage(text) {
        const div = document.createElement("div");
        div.className = "message system";
        div.textContent = text;
        staffMessagesEl.appendChild(div);
        staffMessagesEl.scrollTop = staffMessagesEl.scrollHeight;
    }

    // --- LLM API ---
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

    // --- Staff Message API ---
    async function sendStaffMessage() {
        const text = staffInputEl.value.trim();
        if (!text || staffSending) return;

        staffSending = true;
        staffSendBtn.disabled = true;
        staffInputEl.value = "";
        staffInputEl.style.height = "auto";

        try {
            const response = await fetch(`${BASE}/api/staff-message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
            });

            if (!response.ok) {
                const data = await response.json();
                addStaffSystemMessage("Error: " + (data.error || "Failed to send"));
            }
        } catch (err) {
            addStaffSystemMessage("Connection error: " + err.message);
        } finally {
            staffSending = false;
            staffSendBtn.disabled = false;
            staffInputEl.focus();
        }
    }

    async function resetConversation() {
        try {
            await fetch(`${BASE}/api/reset`, { method: "POST" });
            messagesEl.innerHTML = "";
            staffMessagesEl.innerHTML = "";
            addSystemMessage("Conversation reset. Ask a new question!");
            addStaffSystemMessage("Staff chat reset.");
        } catch (err) {
            addSystemMessage("Failed to reset: " + err.message);
        }
    }

    // --- Suggestion API ---
    let suggestionSending = false;

    async function sendSuggestion() {
        const text = suggestionInput.value.trim();
        if (!text || suggestionSending) return;

        suggestionSending = true;
        suggestionSendBtn.disabled = true;
        suggestionFeedback.textContent = "Submitting...";
        suggestionFeedback.className = "suggestion-feedback";

        try {
            const response = await fetch(`${BASE}/api/suggestion`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ suggestion: text }),
            });

            const data = await response.json();

            if (response.ok) {
                suggestionInput.value = "";
                suggestionInput.style.height = "auto";
                suggestionFeedback.textContent = "Thank you! Your suggestion has been recorded.";
                suggestionFeedback.className = "suggestion-feedback success";
            } else {
                suggestionFeedback.textContent = "Error: " + (data.error || "Failed to submit");
                suggestionFeedback.className = "suggestion-feedback error";
            }
        } catch (err) {
            suggestionFeedback.textContent = "Connection error: " + err.message;
            suggestionFeedback.className = "suggestion-feedback error";
        } finally {
            suggestionSending = false;
            suggestionSendBtn.disabled = false;
        }
    }

    // --- Events ---
    sendBtn.addEventListener("click", sendMessage);
    resetBtn.addEventListener("click", resetConversation);
    staffSendBtn.addEventListener("click", sendStaffMessage);

    inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    staffInputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendStaffMessage();
        }
    });

    // Auto-resize textareas
    function autoResize() {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
    }
    inputEl.addEventListener("input", autoResize);
    staffInputEl.addEventListener("input", autoResize);

    suggestionSendBtn.addEventListener("click", sendSuggestion);
    suggestionInput.addEventListener("input", autoResize);
    suggestionInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendSuggestion();
        }
    });

    // --- Init ---
    setupToggle(toolsToggle, toolsList);
    setupToggle(refsToggle, refsList);
    setupToggle(suggestionsToggle, suggestionsContent);
    loadTools();
    connectWS();
    addSystemMessage("Welcome to BeamtimeHero! Ask questions about your beamline experiment.");
    addStaffSystemMessage("Send a message to beamline staff via Slack.");
})();
