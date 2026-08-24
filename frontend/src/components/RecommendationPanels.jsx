function money(value, currency = "INR") {
  return new Intl.NumberFormat(
    "en-IN",
    {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }
  ).format(value);
}


export default function RecommendationsPanel({
  options = [],
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Ranked recommendations</h2>
          <p>
            Available rooms ranked using deterministic
            matching logic.
          </p>
        </div>
      </div>

      {options.length === 0 ? (
        <div className="empty-state">
          No saved recommendations.
        </div>
      ) : (
        <div className="recommendation-grid">
          {options.map((option, index) => (
            <article
              className="recommendation-card"
              key={option.room_id}
            >
              <span className="option-number">
                Option {index + 1}
              </span>

              <h3>{option.property_name}</h3>
              <p>{option.room_name}</p>

              <dl>
                <dt>Area</dt>
                <dd>{option.area || option.city}</dd>

                <dt>Capacity</dt>
                <dd>{option.capacity} guests</dd>

                <dt>Per night</dt>
                <dd>
                  {money(
                    option.price_per_night,
                    option.currency
                  )}
                </dd>

                <dt>Stay total</dt>
                <dd>
                  {money(
                    option.total_price,
                    option.currency
                  )}
                </dd>

                <dt>Score</dt>
                <dd>{option.score}</dd>
              </dl>

              <ul>
                {option.match_reasons.map(
                  (reason) => (
                    <li key={reason}>
                      {reason}
                    </li>
                  )
                )}
              </ul>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}