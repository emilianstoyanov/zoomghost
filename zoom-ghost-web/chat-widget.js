//zoom-ghost-web\chat-widget.js
document.addEventListener('DOMContentLoaded', () => {
  const chatBubble = document.getElementById("chat-bubble");
  const chatWindow = document.getElementById("chat-window");
  const chatClose = document.getElementById("chat-close");
  const chatEmail = document.getElementById("chat-email");
  const chatMessage = document.getElementById("chat-message");
  const chatSend = document.getElementById("chat-send");
  const chatStatus = document.getElementById("chat-status");
  const chatStatusClose = document.getElementById("chat-status-close");

  if (chatBubble && chatWindow) {
    chatBubble.addEventListener("click", () => {
      chatWindow.classList.remove("hidden");
      chatBubble.classList.add("hidden");
    });
  }

  if (chatClose && chatWindow && chatBubble) {
    chatClose.addEventListener("click", () => {
      chatWindow.classList.add("hidden");
      chatBubble.classList.remove("hidden");
    });
  }

  // Use the existing Supabase client from the main app
  if (chatSend) {
    chatSend.addEventListener("click", async () => {
      if (!chatEmail?.value || !chatMessage?.value) {
        alert("Please fill in all fields");
        return;
      }

      try {
        const { error } = await window.supabase
          .from('support_messages')
          .insert([
            {
              email: chatEmail.value,
              message: chatMessage.value
            }
          ]);

        if (error) throw error;

        showStatusMessage("Message sent successfully!", "success");
        chatEmail.value = '';
        chatMessage.value = '';
      } catch (error) {
        console.error("Error sending message:", error);
        let msg = "Failed to send message";
        if (error && error.message) msg += ": " + error.message;
        showStatusMessage(msg, "error");
      }
    });
  }

  // Add input event listeners for validation
  if (chatEmail && chatMessage) {
    [chatEmail, chatMessage].forEach(el => {
      el.addEventListener("input", () => {
        el.classList.remove("ring", "ring-red-500");
      });
    });
  }

  // Add status close handler
  if (chatStatusClose) {
    chatStatusClose.addEventListener("click", () => {
      chatStatus?.classList.remove("show");
    });
  }
});

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showStatusMessage(message, type = "info") {
  const statusEl = document.getElementById("chat-status");
  const iconEl = document.getElementById("chat-status-icon");
  const textEl = document.getElementById("chat-status-text");

  if (!statusEl || !iconEl || !textEl) return;

  const icons = {
    info: "ℹ️",
    success: "✅",
    error: "❌"
  };

  iconEl.textContent = icons[type] || "ℹ️";
  textEl.textContent = message;

  statusEl.classList.remove("bg-green-500", "bg-red-500", "bg-yellow-500", "bg-blue-500");

  if (type === "success") {
    statusEl.classList.add("bg-green-600");
  } else if (type === "error") {
    statusEl.classList.add("bg-red-600");
  } else {
    statusEl.classList.add("bg-blue-600");
  }

  statusEl.classList.add("show");

  if (statusEl._timeout) clearTimeout(statusEl._timeout);
  statusEl._timeout = setTimeout(() => {
    statusEl.classList.remove("show");
  }, 3500);
}
