/**
 * BeamtimeHero — Chat client
 *
 * Three-panel layout: Sidebar (left) + LLM chat (center) + Staff chat (right)
 *
 * The WebSocket is the event stream for chat traffic: user and assistant
 * turns (from any client), staff messages, tool-status updates, and resets
 * all arrive as WS events. GET /api/history replays the transcript on load
 * and reconnect. Messages carry server-assigned ids; `renderedIds` dedups
 * between the WS event and the sender's own HTTP response.
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
    const toolStatusEl = document.getElementById("tool-status");
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");

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
    const renderedIds = new Set();

    // --- Sidebar ---
    function setupToggle(btn, list) {
        btn.setAttribute("aria-expanded", "false");
        btn.addEventListener("click", function () {
            const open = btn.classList.toggle("open");
            list.classList.toggle("collapsed");
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
    }

    function sidebarNote(list, text) {
        const li = document.createElement("li");
        li.className = "tool-category";
        li.textContent = text;
        list.appendChild(li);
    }

    function sidebarItem(list, name, description) {
        const li = document.createElement("li");
        const nameEl = document.createElement("span");
        nameEl.className = "tool-name";
        nameEl.textContent = name;
        const descEl = document.createElement("span");
        descEl.className = "tool-desc";
        descEl.textContent = description;
        li.appendChild(nameEl);
        li.appendChild(descEl);
        list.appendChild(li);
    }

    async function loadTools() {
        try {
            const response = await fetch(`${BASE}/api/tools`);
            if (!response.ok) {
                sidebarNote(toolsList, "Tool list unavailable");
                sidebarNote(refsList, "Reference list unavailable");
                return;
            }
            const data = await response.json();

            (data.categories || []).forEach(function (group) {
                const header = document.createElement("li");
                header.className = "tool-category";
                header.textContent = group.category;
                toolsList.appendChild(header);

                (group.tools || []).forEach(function (t) {
                    sidebarItem(toolsList, t.name, t.description);
                });
            });

            (data.references || []).forEach(function (r) {
                sidebarItem(refsList, r.name, r.description);
            });
        } catch (err) {
            console.error("Failed to load tools:", err);
            sidebarNote(toolsList, "Tool list unavailable");
        }
    }

    // --- Connection status ---
    function setConnected(connected) {
        statusDot.classList.toggle("disconnected", !connected);
        if (statusText) {
            statusText.textContent = connected ? "connected" : "disconnected";
        }
        statusDot.title = connected ? "Connected" : "Disconnected";
    }

    // --- History ---
    async function loadHistory() {
        try {
            const response = await fetch(`${BASE}/api/history`);
            if (!response.ok) return;
            const data = await response.json();
            const messages = data.messages || [];

            messagesEl.innerHTML = "";
            renderedIds.clear();
            if (messages.length === 0) {
                addSystemMessage("Welcome to BeamtimeHero! Ask questions about your beamline experiment.");
                return;
            }
            messages.forEach(function (m) {
                addMessage(m.role, m.content, m.role === "staff" ? "Staff" : null,
                    m.images, m.id);
            });
        } catch (err) {
            console.error("Failed to load history:", err);
        }
    }

    // --- WebSocket ---
    function connectWS() {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${proto}//${window.location.host}${BASE}/ws`;

        ws = new WebSocket(url);

        ws.onopen = function () {
            setConnected(true);
            console.log("WebSocket connected");
            // Re-sync the transcript: events sent while disconnected are gone.
            loadHistory();
        };

        ws.onmessage = function (event) {
            const data = JSON.parse(event.data);
            if (data.type === "staff_message") {
                // Staff message from #users channel → staff pane
                addStaffMessage("staff", data.text, data.name, data.id);
            } else if (data.type === "staff_in_llm") {
                // Staff message from #llm thread → AI pane
                addMessage("staff", data.text, data.name, null, data.id);
            } else if (data.type === "user_to_staff") {
                // Echo of our message to staff → staff pane
                addStaffMessage("user", data.text, null, data.id);
            } else if (data.type === "user") {
                // A user turn (possibly from another tab/screen) → AI pane
                addMessage("user", data.text, null, null, data.id);
            } else if (data.type === "assistant") {
                // LLM response → AI pane
                showToolStatus(null);
                addMessage("assistant", data.text, null, data.images, data.id);
            } else if (data.type === "tool_status") {
                showToolStatus(data.tools || []);
            } else if (data.type === "reset") {
                messagesEl.innerHTML = "";
                staffMessagesEl.innerHTML = "";
                renderedIds.clear();
                showToolStatus(null);
                addSystemMessage("Conversation reset. Ask a new question!");
                addStaffSystemMessage("Staff chat reset.");
            }
        };

        ws.onclose = function () {
            setConnected(false);
            console.log("WebSocket closed, reconnecting in 3s...");
            setTimeout(connectWS, 3000);
        };

        ws.onerror = function () {
            ws.close();
        };
    }

    // Single heartbeat for whichever socket is current (a per-connection
    // interval would leak one timer per reconnect).
    setInterval(function () {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
        }
    }, 30000);

    // --- LLM Chat Messages ---
    function addMessage(role, text, label, images, id) {
        if (id) {
            if (renderedIds.has(id)) return;
            renderedIds.add(id);
        }

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
            labelEl.textContent = "Hero";
            div.appendChild(labelEl);
        }

        const content = document.createElement("div");
        if (role === "user") {
            content.textContent = text;
        } else {
            // LLM and staff text is untrusted (prompt injection, Slack input)
            // — sanitize the rendered markdown before it touches the DOM.
            content.className = "markdown-content";
            content.innerHTML = DOMPurify.sanitize(marked.parse(text || ""));
        }
        div.appendChild(content);

        // Render plot images
        if (images && images.length > 0) {
            images.forEach(function (b64, i) {
                var img = document.createElement("img");
                img.src = "data:image/png;base64," + b64;
                img.className = "plot-image";
                img.alt = "Plot " + (i + 1) + " of " + images.length;
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
        if (!show) showToolStatus(null);
        if (show) {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }
    }

    function showToolStatus(tools) {
        if (!toolStatusEl) return;
        if (tools && tools.length > 0) {
            toolStatusEl.textContent = "Running: " + tools.join(", ");
            toolStatusEl.classList.add("visible");
        } else {
            toolStatusEl.textContent = "";
            toolStatusEl.classList.remove("visible");
        }
    }

    // --- Staff Chat Messages ---
    function addStaffMessage(role, text, label, id) {
        if (id) {
            if (renderedIds.has(id)) return;
            renderedIds.add(id);
        }

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

    // --- Fetch helper ---
    async function parseJsonResponse(response) {
        // Proxies can answer long-running calls with HTML error pages;
        // surface the status instead of a JSON parse error.
        try {
            return await response.json();
        } catch (err) {
            throw new Error(
                "Server error " + response.status +
                (response.status >= 502 && response.status <= 504
                    ? " — the answer may still be processing; reload to check history"
                    : "")
            );
        }
    }

    // --- LLM API ---
    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text || sending) return;

        sending = true;
        sendBtn.disabled = true;
        inputEl.value = "";
        inputEl.style.height = "auto";

        // Mint the message id client-side so the broadcast `user` event
        // (which arrives before the HTTP response) dedups against this
        // immediate local render.
        const userId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()))
            .replace(/-/g, "");
        addMessage("user", text, null, null, userId);
        showTyping(true);

        try {
            const response = await fetch(`${BASE}/api/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, id: userId }),
            });

            const data = await parseJsonResponse(response);

            if (response.ok) {
                addMessage("assistant", data.response, null, data.images, data.id);
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
                const data = await parseJsonResponse(response);
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
        // The reset destroys the single shared conversation for every
        // connected screen and the Slack threads — make it deliberate.
        if (!confirm("Reset the conversation for ALL connected screens? The assistant loses its context.")) {
            return;
        }
        try {
            await fetch(`${BASE}/api/reset`, { method: "POST" });
            // Panes are cleared by the server's `reset` broadcast; clear
            // locally too in case the WebSocket is down.
            messagesEl.innerHTML = "";
            staffMessagesEl.innerHTML = "";
            renderedIds.clear();
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

            const data = await parseJsonResponse(response);

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
    loadHistory();
    connectWS();
    addStaffSystemMessage("Send a message to beamline staff via Slack.");
})();
