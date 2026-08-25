import {
  useEffect,
  useState,
} from "react";

import {
  checkHealth,
  deleteSession,
  getSessionMessages,
  getSessionState,
  sendChatMessage,
} from "./api";

import ChatPanel from "./components/ChatPanel";
import StatePanel from "./components/StatePanel";
import RecommendationsPanel from "./components/RecommendationPanels";
import "./App.css";


const CURRENT_SESSION_KEY =
  "hotel-agent-session-id";

const SESSION_HISTORY_KEY =
  "hotel-agent-session-history";


function getSessionHistory() {
  try {
    const storedValue = localStorage.getItem(
      SESSION_HISTORY_KEY
    );

    if (!storedValue) {
      return [];
    }

    const parsedHistory = JSON.parse(
      storedValue
    );

    return Array.isArray(parsedHistory)
      ? parsedHistory
      : [];
  } catch (error) {
    console.error(
      "Could not read session history:",
      error
    );

    return [];
  }
}


function saveSessionToHistory(sessionId) {
  const history = getSessionHistory();

  const updatedHistory = [
    sessionId,
    ...history.filter(
      (existingId) => existingId !== sessionId
    ),
  ];

  localStorage.setItem(
    SESSION_HISTORY_KEY,
    JSON.stringify(updatedHistory)
  );

  return updatedHistory;
}

function storeSessionHistory(history) {
  localStorage.setItem(
    SESSION_HISTORY_KEY,
    JSON.stringify(history)
  );

  return history;
}

function createSessionId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }

  return (
    `guest-${Date.now()}-` +
    Math.random().toString(16).slice(2)
  );
}


function createMessage(role, content) {
  return {
    id: createSessionId(),
    role,
    content,
  };
}


function ToolTracePanel({ traces }) {
  return (
    <section className="panel trace-panel">
      <div className="panel-heading">
        <div>
          <h2>Tool calls</h2>

          <p>
            Structured tool arguments and grounded
            results returned during the latest turn.
          </p>
        </div>

        <span className="trace-count">
          {traces.length}
        </span>
      </div>

      {traces.length === 0 ? (
        <div className="empty-state">
          No tools were called in the latest turn.
        </div>
      ) : (
        <div className="trace-list">
          {traces.map((trace, index) => (
            <details
              className="trace"
              key={`${trace.tool}-${index}`}
            >
              <summary>
                <span className="trace-number">
                  {index + 1}
                </span>

                <span className="trace-name">
                  {trace.tool}
                </span>

                <span
                  className={
                    `trace-status ${trace.status}`
                  }
                >
                  {trace.status}
                </span>
              </summary>

              <div className="trace-content">
                <div className="json-block">
                  <h4>Arguments</h4>

                  <pre>
                    {JSON.stringify(
                      trace.arguments,
                      null,
                      2
                    )}
                  </pre>
                </div>

                <div className="json-block">
                  <h4>Result</h4>

                  <pre>
                    {JSON.stringify(
                      trace.result,
                      null,
                      2
                    )}
                  </pre>
                </div>
              </div>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}


export default function App() {
  const [sessionId, setSessionId] = useState(() => {
  const storedSessionId = localStorage.getItem(
    CURRENT_SESSION_KEY
  );

  if (storedSessionId) {
    saveSessionToHistory(storedSessionId);
    return storedSessionId;
  }

  const newSessionId = createSessionId();

  localStorage.setItem(
    CURRENT_SESSION_KEY,
    newSessionId
  );

  saveSessionToHistory(newSessionId);

  return newSessionId;
});

  const [
  deletingSessionId,
  setDeletingSessionId,
] = useState(null);

  const [messages, setMessages] = useState([
    createMessage(
      "agent",
      (
        "Hi! Tell me where you want to stay, " +
        "your dates and how many people are travelling."
      )
    ),
  ]);

  const [state, setState] = useState(null);
  const [action, setAction] = useState(null);
  const [nextAction, setNextAction] =
    useState(null);
  const [traces, setTraces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [backendStatus, setBackendStatus] =
    useState("checking");
  const [
    restoringSession,
    setRestoringSession,
  ] = useState(true);

  const [
  sessionHistory,
  setSessionHistory,
] = useState(() => getSessionHistory());

    useEffect(() => {
    async function verifyBackend() {
      try {
        await checkHealth();

        setBackendStatus("connected");
      } catch (error) {
        console.error(
          "Backend verification failed:",
          error
        );

        setBackendStatus("disconnected");
      }
    }

    verifyBackend();
  }, []);

    useEffect(() => {
    let cancelled = false;

    async function restoreConversation() {
      setRestoringSession(true);

      try {
        const [
          sessionResult,
          messageResult,
        ] = await Promise.all([
          getSessionState(sessionId),
          getSessionMessages(sessionId),
        ]);

        if (cancelled) {
          return;
        }

        setState(sessionResult.state);

        if (messageResult.messages.length > 0) {
          setMessages(
            messageResult.messages.map(
              (message) => ({
                id: message.message_id,
                role:
                  message.role === "guest"
                    ? "guest"
                    : "agent",
                content: message.content,
              })
            )
          );
        }
      } catch (error) {
        /*
         * A new session may not exist in SQLite until its
         * first message is sent. Therefore, a 404 can be
         * treated as an empty conversation.
         */
        console.error(
          "Session restoration failed:",
          error
        );
      } finally {
        if (!cancelled) {
          setRestoringSession(false);
        }
      }
    }

    restoreConversation();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  function handleNewConversation() {
  const newSessionId = createSessionId();

  localStorage.setItem(
    CURRENT_SESSION_KEY,
    newSessionId
  );

  const updatedHistory =
    saveSessionToHistory(newSessionId);

  setSessionHistory(updatedHistory);

  setState(null);
  setAction(null);
  setNextAction(null);
  setTraces([]);

  setMessages([
    createMessage(
      "agent",
      "Where would you like to stay?"
    ),
  ]);

  setSessionId(newSessionId);
}

function handleOpenSession(selectedSessionId) {
  if (selectedSessionId === sessionId) {
    return;
  }

  localStorage.setItem(
    CURRENT_SESSION_KEY,
    selectedSessionId
  );

  const updatedHistory =
    saveSessionToHistory(selectedSessionId);

  setSessionHistory(updatedHistory);

  setState(null);
  setAction(null);
  setNextAction(null);
  setTraces([]);
  setMessages([]);

  setSessionId(selectedSessionId);
}

async function handleDeleteSession(
  sessionIdToDelete
) {
  const confirmed = window.confirm(
    "Delete this conversation permanently? "
      + "Its messages, state, tool traces and "
      + "booking holds will be removed."
  );

  if (!confirmed) {
    return;
  }

  setDeletingSessionId(sessionIdToDelete);

  try {
    /*
     * Delete the session and all related records
     * from SQLite first.
     */
    await deleteSession(sessionIdToDelete);

    const remainingHistory =
      sessionHistory.filter(
        (storedSessionId) =>
          storedSessionId !==
          sessionIdToDelete
      );

    storeSessionHistory(remainingHistory);
    setSessionHistory(remainingHistory);

    /*
     * If an inactive session was deleted, the
     * currently opened conversation is unaffected.
     */
    if (sessionIdToDelete !== sessionId) {
      return;
    }

    /*
     * If the currently active session was deleted,
     * open another saved session if one exists.
     */
    if (remainingHistory.length > 0) {
      const nextSessionId =
        remainingHistory[0];

      localStorage.setItem(
        CURRENT_SESSION_KEY,
        nextSessionId
      );

      setMessages([]);
      setState(null);
      setAction(null);
      setNextAction(null);
      setTraces([]);

      /*
       * This triggers the restoration useEffect.
       */
      setSessionId(nextSessionId);

      return;
    }

    /*
     * If no sessions remain, create a fresh local
     * conversation. It will be saved to SQLite after
     * the guest sends the first message.
     */
    const newSessionId =
      createSessionId();

    localStorage.setItem(
      CURRENT_SESSION_KEY,
      newSessionId
    );

    const newHistory = [
      newSessionId,
    ];

    storeSessionHistory(newHistory);
    setSessionHistory(newHistory);

    setMessages([
      createMessage(
        "agent",
        "Where would you like to stay?"
      ),
    ]);

    setState(null);
    setAction(null);
    setNextAction(null);
    setTraces([]);

    setSessionId(newSessionId);
  } catch (error) {
    console.error(
      "Session deletion failed:",
      error
    );

    window.alert(
      `Could not delete conversation: ${
        error.message
      }`
    );
  } finally {
    setDeletingSessionId(null);
  }
}


  async function handleSend(message) {
    setMessages((current) => [
      ...current,
      createMessage("guest", message),
    ]);

    setLoading(true);

    try {
      const result = await sendChatMessage(
        sessionId,
        message
      );

      setMessages((current) => [
        ...current,
        createMessage(
          "agent",
          result.response
        ),
      ]);

      setState(result.state);
      setAction(result.action);
      setNextAction(result.next_action);
      setTraces(result.tool_traces || []);
      setBackendStatus("connected");
    } catch (error) {
      setMessages((current) => [
        ...current,
        createMessage(
          "agent",
          `Request failed: ${error.message}`
        ),
      ]);

      setAction("request_error");
      setNextAction("check_backend");
      setTraces([]);
      setBackendStatus("disconnected");
    } finally {
      setLoading(false);
    }
  }

  if (restoringSession) {
    return (
      <div className="app restoring-app">
        <div className="panel">
          Restoring previous conversation...
        </div>
      </div>
    );
  }

  return (
    <div className="app">
       <aside className="conversation-sidebar">
       <div className="sidebar-header">
          <h2>Conversations</h2>

        <button
          type="button"
          className="new-conversation-button"
          onClick={handleNewConversation}
        >
          + New conversation
        </button>
      </div>

      <div className="conversation-list">
        {sessionHistory.length === 0 ? (
          <p className="empty-history">
            No previous conversations
          </p>
        ) : (
          sessionHistory.map(
  (storedSessionId, index) => {
    const isCurrent =
      storedSessionId === sessionId;

    const isDeleting =
      deletingSessionId ===
      storedSessionId;

    return (
      <div
        key={storedSessionId}
        className={
          isCurrent
            ? "conversation-row active"
            : "conversation-row"
        }
      >
        <button
          type="button"
          className="conversation-open-button"
          onClick={() =>
            handleOpenSession(
              storedSessionId
            )
          }
          disabled={isDeleting}
        >
          <span>
            {isCurrent
              ? "Current conversation"
              : `Conversation ${
                  sessionHistory.length -
                  index
                }`}
          </span>

        </button>

        <button
          type="button"
          className="conversation-delete-button"
          onClick={() =>
            handleDeleteSession(
              storedSessionId
            )
          }
          disabled={isDeleting}
          aria-label={
            "Delete conversation "
              + storedSessionId
          }
          title="Delete conversation"
        >
          {isDeleting ? "…" : "×"}
        </button>
      </div>
    );
  }
)
        )}
      </div>
    </aside>

      <main className="main-content">
      <header className="app-header">
        <div>
          <span className="eyebrow">
            Hotel booking assistant
          </span>

          <h1>Mira!</h1>

          <p>
            Test conversation memory, hotel search,
            availability, pricing and grounded answers.
          </p>
        </div>

        <div className="header-actions">
          <div
            className={`backend-status ${backendStatus}`}
          >
            <span className="status-dot" />

            {backendStatus === "checking" &&
              "Checking backend"}

            {backendStatus === "connected" &&
              "Backend connected"}

            {backendStatus === "disconnected" &&
              "Backend disconnected"}
          </div>
        </div>
      </header>

      

      <main className="dashboard">
        <ChatPanel
          messages={messages}
          loading={loading}
          onSend={handleSend}
        />

        <StatePanel
          state={state}
          action={action}
          nextAction={nextAction}
        />
       <RecommendationsPanel options={
    state?.last_search_results || []}></RecommendationsPanel>
        <ToolTracePanel traces={traces} />
      </main>
      </main>
    </div>
  );

}