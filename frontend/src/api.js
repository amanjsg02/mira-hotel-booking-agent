/*
 * Backend base URL.
 *
 * Local development:
 *   http://localhost:8000
 *
 * Production:
 *   Set VITE_API_BASE_URL in Vercel to your Render URL.
 *
 * Example:
 *   https://mera-hotel-agent-api.onrender.com
 */
const configuredApiUrl =
  import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = (
  configuredApiUrl ||
  "http://localhost:8000"
).replace(/\/+$/, "");


/*
 * Convert a backend response into JSON and provide a
 * readable error when the request fails.
 *
 * This also supports successful responses that do not
 * contain a JSON body.
 */
async function parseResponse(response) {
  const contentType =
    response.headers.get("content-type") || "";

  let body = null;

  try {
    if (
      contentType.includes("application/json")
    ) {
      body = await response.json();
    } else {
      const text = await response.text();
      body = text || null;
    }
  } catch {
    body = null;
  }

  if (!response.ok) {
    let message;

    if (
      body &&
      typeof body === "object"
    ) {
      message =
        body.detail ||
        body.message ||
        body.error;
    }

    if (!message && typeof body === "string") {
      message = body;
    }

    if (!message) {
      message =
        `Request failed with status ` +
        `${response.status}`;
    }

    throw new Error(
      typeof message === "string"
        ? message
        : JSON.stringify(message)
    );
  }

  return body;
}


/*
 * Safely prepare a session ID for use inside a URL.
 */
function encodeSessionId(sessionId) {
  if (
    typeof sessionId !== "string" ||
    !sessionId.trim()
  ) {
    throw new Error(
      "A valid session ID is required."
    );
  }

  return encodeURIComponent(
    sessionId.trim()
  );
}


/*
 * Generate a unique request ID for chat requests.
 */
function createRequestId() {
  if (
    globalThis.crypto &&
    typeof globalThis.crypto.randomUUID ===
      "function"
  ) {
    return globalThis.crypto.randomUUID();
  }

  return (
    `req-${Date.now()}-` +
    Math.random()
      .toString(16)
      .slice(2)
  );
}


/*
 * Check whether the FastAPI backend is available.
 */
export async function checkHealth() {
  const response = await fetch(
    `${API_BASE_URL}/health`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    }
  );

  return parseResponse(response);
}


/*
 * Send a guest message to the hotel agent.
 */
export async function sendChatMessage(
  sessionId,
  message,
  requestId = createRequestId()
) {
  if (
    typeof message !== "string" ||
    !message.trim()
  ) {
    throw new Error(
      "A message is required."
    );
  }

  const response = await fetch(
    `${API_BASE_URL}/api/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        request_id: requestId,
        session_id: sessionId,
        message: message.trim(),
      }),
    }
  );

  return parseResponse(response);
}


/*
 * Retrieve one session and its current state.
 */
export async function getSession(
  sessionId
) {
  const encodedSessionId =
    encodeSessionId(sessionId);

  const response = await fetch(
    `${API_BASE_URL}/api/sessions/` +
      encodedSessionId,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    }
  );

  return parseResponse(response);
}


/*
 * Retrieve the current state for a session.
 *
 * This endpoint is currently the same as getSession().
 * The separate function is retained so your existing
 * React components do not need to change.
 */
export async function getSessionState(
  sessionId
) {
  return getSession(sessionId);
}


/*
 * Retrieve all stored messages for a session.
 */
export async function getSessionMessages(
  sessionId
) {
  const encodedSessionId =
    encodeSessionId(sessionId);

  const response = await fetch(
    `${API_BASE_URL}/api/sessions/` +
      `${encodedSessionId}/messages`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    }
  );

  return parseResponse(response);
}


/*
 * Permanently delete a session from the backend
 * database.
 */
export async function deleteSession(
  sessionId
) {
  const encodedSessionId =
    encodeSessionId(sessionId);

  const response = await fetch(
    `${API_BASE_URL}/api/sessions/` +
      encodedSessionId,
    {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    }
  );

  return parseResponse(response);
}


/*
 * Retrieve information about the configured AI agent.
 */
export async function getAgentStatus() {
  const response = await fetch(
    `${API_BASE_URL}/api/agent/status`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    }
  );

  return parseResponse(response);
}