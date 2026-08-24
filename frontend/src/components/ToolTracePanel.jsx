function JsonBlock({ title, value }) {
  return (
    <div className="json-block">
      <h4>{title}</h4>

      <pre>
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}


export default function ToolTracePanel({
  traces,
}) {
  return (
    <section className="panel trace-panel">
      <div className="panel-heading">
        <div>
          <h2>Tool calls</h2>
          <p>
            Structured tools executed during the latest
            message.
          </p>
        </div>

        <span className="trace-count">
          {traces.length}
        </span>
      </div>

      {traces.length === 0 ? (
        <div className="empty-state">
          No tools were called for the latest message.
          This is normal when required information is
          missing.
        </div>
      ) : (
        <div className="trace-list">
          {traces.map((trace, index) => (
            <details
              className="trace"
              key={`${trace.tool}-${index}`}
              open={index === 0}
            >
              <summary>
                <span className="trace-number">
                  {index + 1}
                </span>

                <span className="trace-name">
                  {trace.tool}
                </span>

                <span
                  className={`trace-status ${
                    trace.status === "success"
                      ? "success"
                      : "error"
                  }`}
                >
                  {trace.status}
                </span>
              </summary>

              <div className="trace-content">
                <JsonBlock
                  title="Arguments"
                  value={trace.arguments}
                />

                <JsonBlock
                  title="Result"
                  value={trace.result}
                />
              </div>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}