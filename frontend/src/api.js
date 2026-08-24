const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";



export async function deleteSession(
  sessionId
) {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    const errorBody = await response
      .json()
      .catch(() => null);

    throw new Error(
      errorBody?.detail ||
      `Could not delete session: ${
        response.status
      }`
    );
  }

  return response.json();
}


async function parseResponse(response) {
  let body;

  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const message =
      body?.detail ||
      body?.message ||
      `Request failed with status ${response.status}`;

    throw new Error(
      typeof message === "string"
        ? message
        : JSON.stringify(message)
    );
  }

  return body;
}


export async function checkHealth() {
  const response = await fetch(
    `${API_BASE_URL}/health`
  );

  return parseResponse(response);
}



function createRequestId() {
  if (crypto?.randomUUID) {
    return crypto.randomUUID();
  }

  return (
    `req-${Date.now()}-` +
    Math.random().toString(16).slice(2)
  );
}


export async function sendChatMessage(
  sessionId,
  message,
  requestId = createRequestId()
) {
  const response = await fetch(
    `${API_BASE_URL}/api/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        request_id: requestId,
        session_id: sessionId,
        message,
      }),
    }
  );

  return parseResponse(response);
}


export async function getSessionMessages(
  sessionId
) {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/` +
    `${sessionId}/messages`
  );

  return parseResponse(response);
}


export async function getSessionState(
  sessionId
) {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/` +
    `${sessionId}`
  );

  return parseResponse(response);
}

export async function getSession(sessionId) {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}`
  );

  return parseResponse(response);
}



export async function getAgentStatus() {
  const response = await fetch(
    `${API_BASE_URL}/api/agent/status`
  );

  return parseResponse(response);
}