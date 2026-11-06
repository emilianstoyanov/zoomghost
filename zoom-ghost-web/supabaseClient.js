// zoom-ghost-web/supabaseClient.js

const zoomghostConfig = window.ZOOMGHOST_CONFIG || {};
const SUPABASE_URL = zoomghostConfig.SUPABASE_URL;
const SUPABASE_KEY = zoomghostConfig.SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error("ZoomGhost: missing config.js. Copy config.example.js to config.js and set SUPABASE_URL and SUPABASE_ANON_KEY.");
} else if (typeof supabase !== "undefined" && typeof supabase.createClient === "function") {
  const client = supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storageKey: "zoom-ghost-auth",
      storage: window.localStorage
    }
  });

  window.supabase = client;
} else {
  console.error("Supabase client library not loaded");
}
