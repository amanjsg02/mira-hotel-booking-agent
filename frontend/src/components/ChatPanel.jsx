import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
export default function ChatPanel({
  messages,
  loading,
  onSend,
}) {
  const [input, setInput] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();

    const message = input.trim();

    if (!message || loading) {
      return;
    }

    setInput("");

    await onSend(message);
  }

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <section className="panel chat-panel">
      <div className="panel-heading">
        <div>
          <h2>Guest conversation</h2>
          <p>
            Send messages using the same session to test
            conversation memory.
          </p>
        </div>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="empty-state">
            Start by telling the agent where and when
            you want to stay.
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`message-row ${message.role}`}
          >
            <div className="message">
              <div className="message-label">
                {message.role === "guest"
                  ? "Guest"
                  : "Agent"}
              </div>

              <div className="message-content">
               {message.role === "agent" ? (
    <div className="markdown-response">
  <ReactMarkdown
    remarkPlugins={[
      remarkGfm,
      remarkBreaks,
    ]}
    components={{
      a: ({
        node,
        children,
        ...properties
      }) => (
        <a
          {...properties}
          target="_blank"
          rel="noreferrer"
        >
          {children}
        </a>
      ),
    }}
  >
    {message.content}
  </ReactMarkdown>
</div>
  ) : (
    <p className="guest-message-text">
      {message.content}
    </p>
  )}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="message-row agent">
            <div className="message">
              <div className="message-label">
                Agent
              </div>

              <div className="typing-indicator">
                Processing message...
              </div>
            </div>
          </div>
        )}
      </div>

      <form
        className="chat-form"
        onSubmit={handleSubmit}
      >
        <textarea
          value={input}
          onChange={(event) =>
            setInput(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder={
            "Example: Need something in Goa next " +
            "weekend for 4 guests under 20k"
          }
          rows={3}
          disabled={loading}
        />

        <button
          type="submit"
          className="primary-button"
          disabled={loading || !input.trim()}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </section>
  );
}