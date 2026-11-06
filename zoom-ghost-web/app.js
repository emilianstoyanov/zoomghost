//zoom-ghost-web/app.js

// Shared functions
window.showToast = showToast;

const authChannel = new BroadcastChannel("auth");

const zoomghostConfig = window.ZOOMGHOST_CONFIG || {};
const API_BASE_URL = String(zoomghostConfig.API_BASE_URL || "").replace(/\/$/, "");
const SUPABASE_ANON_KEY = zoomghostConfig.SUPABASE_ANON_KEY || "";

// Show the views
function updateUIOnSession(session) {
  const isLoggedIn = !!session?.user;
  document.getElementById("view-landing")?.classList.toggle("hidden", isLoggedIn);
  document.getElementById("view-dashboard")?.classList.toggle("hidden", !isLoggedIn);
  document.getElementById("nav-login-btn")?.classList.toggle("hidden", isLoggedIn);
  document.getElementById("nav-logout-btn")?.classList.toggle("hidden", !isLoggedIn);
}

// Reset the interface
function resetInterface() {
  const slackBtn = document.getElementById("slack-btn");
  const disconnectSlack = document.getElementById("disconnect-slack");

  const zoomBtn = document.getElementById("zoom-btn");
  const disconnectZoom = document.getElementById("disconnect-zoom");

  if (slackBtn) {
    slackBtn.innerHTML = `<i class="ri-slack-line"></i> Connect Slack`;
    slackBtn.disabled = false;
    slackBtn.classList.remove("bg-green-500/20");
  }

  disconnectSlack?.classList.add("hidden");

  if (zoomBtn) {
    zoomBtn.innerHTML = `<i class="ri-vidicon-line"></i> Connect Zoom`;
    zoomBtn.disabled = false;
    zoomBtn.classList.remove("bg-green-500/20");
  }

  disconnectZoom?.classList.add("hidden");
}

// Main session
async function setupUserSession(user) {
  if (!user?.id) return;
  resetInterface();
  console.log("[ZoomGhost] setupUserSession() called with:", user);

  try {
    await window.supabase.from("users").upsert({ id: user.id, email: user.email });

    // Slack
    const { data: slackToken } = await window.supabase
      .from("oauth_tokens")
      .select("metadata")
      .eq("user_id", user.id)
      .eq("provider", "slack")
      .eq("is_active", true)
      .maybeSingle();

    const slackBtn = document.getElementById("slack-btn");
    const disconnectSlack = document.getElementById("disconnect-slack");
    const connectSlackLink = document.getElementById("connect-slack-link");

    if (slackToken?.metadata?.username) {
      slackBtn.innerHTML = `<i class="ri-slack-line"></i> Connected as @${slackToken.metadata.username}`;
      slackBtn.disabled = true;
      slackBtn.classList.add("bg-green-500/20");
      disconnectSlack?.classList.remove("hidden");
    } else if (slackBtn && connectSlackLink) {
      connectSlackLink.href = `${API_BASE_URL}/api/slack/install?uid=${user.id}`;
      slackBtn.addEventListener("click", () => {
        window.open(connectSlackLink.href, "_blank");
      }, { once: true });
    }

    disconnectSlack?.addEventListener("click", async () => {
      try {
        await window.supabase
          .from("oauth_tokens")
          .update({ is_active: false })
          .eq("user_id", user.id)
          .eq("provider", "slack");
        showToast("Slack disconnected", "success");
        resetInterface();
        await setupUserSession(user);
      } catch {
        showToast("Failed to disconnect Slack", "error");
      }
    });

    // Zoom
    const { data: zoomToken } = await window.supabase
      .from("oauth_tokens")
      .select("metadata")
      .eq("user_id", user.id)
      .eq("provider", "zoom")
      .eq("is_active", true)
      .maybeSingle();

    const zoomBtn = document.getElementById("zoom-btn");
    const disconnectZoom = document.getElementById("disconnect-zoom");

    if (zoomToken?.metadata?.email) {
      zoomBtn.innerHTML = `<i class="ri-vidicon-line"></i> Connected as ${zoomToken.metadata.email}`;
      zoomBtn.disabled = true;
      zoomBtn.classList.add("bg-green-500/20");
      disconnectZoom?.classList.remove("hidden");
      await loadZoomRecordings();
    } else if (zoomBtn) {
      zoomBtn.addEventListener("click", () => {
        window.open(
          `${API_BASE_URL}/api/zoom/install?uid=${user.id}`,
          "_blank"
        );
      }, { once: true });
    }

    disconnectZoom?.addEventListener("click", async () => {
      try {
        await window.supabase
          .from("oauth_tokens")
          .update({ is_active: false })
          .eq("user_id", user.id)
          .eq("provider", "zoom");
        showToast("Zoom disconnected", "success");
        resetInterface();
        await setupUserSession(user);
      } catch {
        showToast("Failed to disconnect Zoom", "error");
      }
    });

  } catch (err) {
    showToast("Session setup failed", "error");
    console.error(err);
  }
}

// Load recordings
async function loadZoomRecordings() {
  const container = document.getElementById("recordings-list");
  if (!container) return;
  container.innerHTML = "<p class='text-white/70'>📡 Loading Zoom recordings...</p>";

  try {
    const { data: { session } } = await window.supabase.auth.getSession();
    const token = session?.access_token;
    const userId = session?.user?.id;

    const res = await fetch(`${API_BASE_URL}/api/recordings?user_id=${userId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "apikey": SUPABASE_ANON_KEY
      },
    });

    if (!res.ok) throw new Error("Failed to load Zoom recordings.");
    const result = await res.json();
    const recordings = result.recordings || [];

    container.innerHTML = "";
    if (recordings.length === 0) {
      container.innerHTML = "<p class='text-white/50 italic'>No recordings found.</p>";
      return;
    }

    recordings.forEach((rec) => {
      const el = document.createElement("div");
      el.className = "bg-white/5 p-3 rounded border border-white/10";
      el.innerHTML = `
        <div class="font-medium mb-1">${rec.topic || "Untitled"}</div>
        <div class="text-xs text-white/60 mb-2">🕒 ${new Date(rec.start_time).toLocaleString()}</div>
        <a href="${rec.recording_files?.[0]?.download_url}" target="_blank" class="text-indigo-300 text-sm underline">
          🔗 View on Zoom
        </a>
      `;
      container.appendChild(el);
    });

  } catch (err) {
    container.innerHTML = `<p class="text-red-400 text-sm">❌ Error: ${err.message}</p>`;
  }
}

// Log out
async function handleLogout() {
  try {
    await window.supabase.auth.signOut();
    showToast("Logged out", "success");
    authChannel.postMessage("SIGNED_OUT");
    updateUIOnSession(null);
  } catch {
    showToast("Logout failed", "error");
  }
}

// Toast
function showToast(message, type = "info") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg z-50 ${
    type === "error" ? "bg-red-500" : type === "success" ? "bg-green-500" : "bg-blue-500"
  }`;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3000);
}

// Log in
function handleLogin() {
  document.getElementById("auth-modal")?.classList.remove("hidden");
  document.getElementById("email-input")?.focus();
}

// Magic Link Login
async function handleMagicLinkLogin(email) {
  const btn = document.getElementById("send-link");
  const progress = document.getElementById("progress-bar");
  const viewStart = document.getElementById("view-start");
  const viewCheck = document.getElementById("view-check-email");

  if (!email) return showToast("Enter your email", "error");

  btn.disabled = true;
  btn.innerHTML = '<i class="ri-loader-4-line animate-spin"></i> Sending...';
  progress?.classList.remove("hidden");

  try {
    const { error } = await window.supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: window.location.origin,
        flowType: "pkce"
      }
    });
    if (error) throw error;
    viewStart?.classList.add("hidden");
    viewCheck?.classList.remove("hidden");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="ri-shield-keyhole-line"></i> Secure Access';
    progress?.classList.add("hidden");
  }
}

// DOM Ready
document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("nav-login-btn")?.addEventListener("click", handleLogin);
  document.getElementById("landing-login-btn")?.addEventListener("click", handleLogin);
  document.getElementById("nav-logout-btn")?.addEventListener("click", handleLogout);

  const emailInput = document.getElementById("email-input");
  document.getElementById("send-link")?.addEventListener("click", () => {
    handleMagicLinkLogin(emailInput?.value);
  });
  emailInput?.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleMagicLinkLogin(emailInput.value);
  });

  const { data: { session } } = await window.supabase.auth.getSession();
  console.log("[ZoomGhost] Initial session:", session);
  updateUIOnSession(session);

  requestAnimationFrame(() => {
    if (session?.user) setupUserSession(session.user);
  });

  const urlParams = new URLSearchParams(location.search);
  if (urlParams.get("slack") === "connected" || urlParams.get("zoom") === "connected") {
    window.history.replaceState({}, document.title, window.location.pathname);
    requestAnimationFrame(() => {
      if (session?.user) setupUserSession(session.user);
    });
  }
});

// Auth change
window.supabase.auth.onAuthStateChange(async (event, session) => {
  console.log("[ZoomGhost] Auth state change:", event);
  updateUIOnSession(session);
  if (event === "SIGNED_IN" && session?.user) {
    authChannel.postMessage("SIGNED_IN");
    requestAnimationFrame(() => setupUserSession(session.user));
  }
  if (event === "SIGNED_OUT") {
    authChannel.postMessage("SIGNED_OUT");
    showToast("Signed out", "info");
  }
});

// Broadcast sync
authChannel.onmessage = async (event) => {
  const { data: { session } } = await window.supabase.auth.getSession();
  if (event.data === "SIGNED_IN") {
    updateUIOnSession(session);
    requestAnimationFrame(() => {
      if (session?.user) setupUserSession(session.user);
    });
  }
  if (event.data === "SIGNED_OUT") {
    updateUIOnSession(null);
  }
};

// Multi-tab sync
window.addEventListener("storage", async (event) => {
  if (event.key?.startsWith("sb-")) {
    const { data: { session } } = await window.supabase.auth.getSession();
    updateUIOnSession(session);
    requestAnimationFrame(() => {
      if (session?.user) setupUserSession(session.user);
    });
  }
});
