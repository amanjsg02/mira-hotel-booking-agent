function formatDate(value) {
  if (!value) {
    return "Not provided";
  }

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }
  ).format(date);
}


function formatMoney(value) {
  if (value === null || value === undefined) {
    return "Not provided";
  }

  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }
  ).format(value);
}


function StateItem({ label, value }) {
  return (
    <div className="state-item">
      <span className="state-label">
        {label}
      </span>

      <span className="state-value">
        {value}
      </span>
    </div>
  );
}


export default function StatePanel({
  state,
  action,
  nextAction,
}) {
  const totalGuests =
    state?.guests?.adults === null ||
    state?.guests?.adults === undefined
      ? null
      : state.guests.adults +
        (state.guests.children || 0);

  return (
    <section className="panel state-panel">
      <div className="panel-heading">
        <div>
          <h2>Current state</h2>
          <p>
            Information currently remembered by the
            backend.
          </p>
        </div>
      </div>

      {!state ? (
        <div className="empty-state">
          State will appear after the first message.
        </div>
      ) : (
        <>
          <div className="state-grid">
            <StateItem
              label="Destination"
              value={
                state.destination ||
                "Not provided"
              }
            />

            <StateItem
              label="Check-in"
              value={formatDate(state.check_in)}
            />

            <StateItem
              label="Check-out"
              value={formatDate(state.check_out)}
            />

            <StateItem
              label="Adults"
              value={
                state.guests?.adults ??
                "Not provided"
              }
            />

            <StateItem
              label="Children"
              value={
                state.guests?.children ?? 0
              }
            />

            <StateItem
              label="Total guests"
              value={
                totalGuests ??
                "Not provided"
              }
            />

            <StateItem
              label="Budget/night"
              value={formatMoney(
                state.budget_per_night
              )}
            />

            <StateItem
              label="Amenities"
              value={
                state.preferred_amenities
                  ?.length
                  ? state.preferred_amenities
                      .map((item) =>
                        item.replaceAll("_", " ")
                      )
                      .join(", ")
                  : "None"
              }
            />

            <StateItem
              label="Special requirements"
              value={
                state.special_requirements
                  ?.length
                  ? state.special_requirements
                      .map((item) =>
                        item.replaceAll("_", " ")
                      )
                      .join(", ")
                  : "None"
              }
            />

            <StateItem
              label="Selected property"
              value={
                state.selected_property_id ||
                "None"
              }
            />

            <StateItem
              label="Selected room"
              value={
                state.selected_room_id ||
                "None"
              }
            />
          </div>

          <div className="decision-section">
            <h3>Structured decision</h3>

            <StateItem
              label="Current action"
              value={action || "None"}
            />

            <StateItem
              label="Next action"
              value={nextAction || "None"}
            />
          </div>

          <details className="raw-state">
            <summary>View raw state JSON</summary>

            <pre>
              {JSON.stringify(state, null, 2)}
            </pre>
          </details>
        </>
      )}
    </section>
  );
}