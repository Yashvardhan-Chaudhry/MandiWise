import React, { useEffect, useRef, useState } from "react";
import { api, money, candidateMarkets } from "./lib";

export default function Rankings({ t }) {
  const [crops, setCrops] = useState([]),
    [crop, setCrop] = useState("");
  const [markets, setMarkets] = useState([]),
    [selected, setSelected] = useState({});
  const [quantity, setQuantity] = useState(""),
    [origin, setOrigin] = useState("");
  const [result, setResult] = useState(null),
    [error, setError] = useState("");
  const [loading, setLoading] = useState(true),
    [sending, setSending] = useState(false);
  const [retry, setRetry] = useState(0);
  const revision = useRef(0),
    submitting = useRef(false);
  const invalidate = () => {
    revision.current++;
    setResult(null);
    setError("");
  };
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api("/v1/commodities")
      .then((data) => {
        if (active) {
          setCrops(data.commodities);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.status === 404 ? t("rankMissing") : e.message);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [retry]);
  useEffect(() => {
    if (!crop) return;
    let active = true;
    setLoading(true);
    api(`/v1/markets?commodity=${encodeURIComponent(crop)}`)
      .then((data) => {
        if (active) {
          setMarkets(candidateMarkets(data.markets));
          setLoading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [crop, retry]);
  async function submit(e) {
    e.preventDefault();
    if (submitting.current) return;
    const candidates = markets
      .filter((m) => Object.hasOwn(selected, m.id))
      .map((m) => ({
        market: m.market,
        district: m.district,
        distance_km: selected[m.id],
      }));
    if (!candidates.length) {
      setError(t("rankChoose"));
      return;
    }
    submitting.current = true;
    setSending(true);
    setError("");
    setResult(null);
    const requestRevision = revision.current;
    try {
      const data = await api("/v1/rankings", {
        commodity: crop,
        quantity_quintals: quantity,
        candidates,
      });
      if (revision.current === requestRevision) setResult(data);
    } catch (e) {
      if (revision.current === requestRevision)
        setError(e.status === 404 ? t("rankMissing") : e.message);
    } finally {
      submitting.current = false;
      setSending(false);
    }
  }
  return (
    <>
      <div className="heading">
        <div>
          <p className="eyebrow">MANDIWISE / PUNJAB</p>
          <h1>{t("rankings")}</h1>
          <p>{t("rankIntro")}</p>
        </div>
      </div>
      <div className="notice warning">
        <strong>{t("rankDemo")}</strong>
        <p>{t("rankCaveat")}</p>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
          <button
            type="button"
            onClick={() => {
              invalidate();
              setRetry((r) => r + 1);
            }}
          >
            {t("rankRetry")}
          </button>
        </div>
      )}
      <form onSubmit={submit} className="card ranking-form">
        <h2>{t("rankInputs")}</h2>
        <div className="grid2">
          <label className="field">
            <span>{t("rankOrigin")}</span>
            <input
              required
              maxLength={160}
              value={origin}
              onChange={(e) => {
                invalidate();
                setOrigin(e.target.value);
              }}
            />
          </label>
          <label className="field">
            <span>{t("crop")}</span>
            <select
              required
              value={crop}
              onChange={(e) => {
                invalidate();
                setSelected({});
                setMarkets([]);
                setCrop(e.target.value);
              }}
            >
              <option value="">{t("rankSelectCrop")}</option>
              {crops.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("quantity")}</span>
            <input
              required
              type="number"
              min="0.01"
              max="1000"
              step="0.01"
              value={quantity}
              onChange={(e) => {
                invalidate();
                setQuantity(e.target.value);
              }}
            />
          </label>
        </div>
        <h3>
          {t("rankCandidates")} ({Object.keys(selected).length}/10)
        </h3>
        <p className="muted">{t("rankDistances")}</p>
        {loading && <p role="status">{t("loading")}</p>}
        {!loading && crop && !markets.length && <p>{t("empty")}</p>}
        <div className="ranking-candidates">
          {markets.map((m) => {
            const chosen = Object.hasOwn(selected, m.id);
            return (
              <div className="ranking-candidate" key={m.id}>
                <label className="ranking-check">
                  <input
                    type="checkbox"
                    checked={chosen}
                    disabled={!chosen && Object.keys(selected).length >= 10}
                    onChange={(e) => {
                      invalidate();
                      const next = { ...selected };
                      if (e.target.checked) next[m.id] = "";
                      else delete next[m.id];
                      setSelected(next);
                    }}
                  />
                  <span>
                    <strong>{m.market}</strong>
                    <small>{m.district}</small>
                  </span>
                </label>
                {chosen && (
                  <label className="field">
                    <span>
                      {t("distance")} — {m.market}, {m.district}
                    </span>
                    <input
                      type="number"
                      required
                      min="0"
                      max="2000"
                      step="0.001"
                      value={selected[m.id]}
                      onChange={(e) => {
                        invalidate();
                        setSelected({ ...selected, [m.id]: e.target.value });
                      }}
                    />
                  </label>
                )}
              </div>
            );
          })}
        </div>
        <button
          disabled={
            loading || sending || !crop || !Object.keys(selected).length
          }
          type="submit"
        >
          {sending ? t("working") : t("rankCalculate")}
        </button>
      </form>
      {result && (
        <section aria-live="polite" className="ranking-results">
          <h2>
            {t("rankResults")} — {origin}
          </h2>
          <p>
            {result.commodity} · {result.quantity_quintals} {t("rankQuintals")}{" "}
            · {t("rankAsOf")}: {result.as_of}
          </p>
          {result.is_demo && (
            <div className="notice warning">
              <strong>{t("rankDemo")}</strong>
              <ul>
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {!result.is_demo &&
            result.warnings?.map((w, i) => (
              <div className="notice warning" key={i}>
                {w}
              </div>
            ))}
          <p>{t("rankQuality")}</p>
          {!result.results.length && <p>{t("rankNoResults")}</p>}
          {result.results.map((offer, index) => (
            <article
              className={`card ranking-offer ${offer.is_stale ? "ranking-stale" : ""}`}
              key={`${offer.district}:${offer.market}:${offer.variety}:${offer.grade}:${index}`}
            >
              <p className="eyebrow">
                #{index + 1} ·{" "}
                {index === 0 ? t("rankBest") : t("rankAlternative")}
              </p>
              <h3>
                {offer.market} · {offer.district}
              </h3>
              <p>
                {t("variety")}: {offer.variety || t("rankUnknown")} ·{" "}
                {t("grade")}: {offer.grade || t("rankUnknown")}
              </p>
              <p className="ranking-date">
                {t("date")}: {offer.price_date} · {offer.age_days}{" "}
                {t("rankDays")}{" "}
                {offer.is_stale && <strong> · {t("rankStale")}</strong>}
              </p>
              <p>
                {offer.distance_km} km · {t("modal")}:{" "}
                {money(offer.modal_price)}
              </p>
              <div className="ranking-net">
                <span>{t("rankNet")}</span>
                <strong>{money(offer.net)}</strong>
                <p>
                  {t("rankRange")}:{" "}
                  <b>
                    {money(offer.net_min)} – {money(offer.net_max)}
                  </b>
                </p>
              </div>
              <p className="muted">{t("rankRangeNote")}</p>
              <dl className="ranking-breakdown">
                {[
                  "gross",
                  "commission",
                  "market_fee",
                  "handling",
                  "transport",
                  "net",
                ].map((key) => (
                  <div key={key}>
                    <dt>{t(`rank_${key}`)}</dt>
                    <dd>{money(offer[key])}</dd>
                  </div>
                ))}
              </dl>
              <p>
                {t("vehicles")}:{" "}
                {offer.vehicles.map((v) => `${v.count} × ${v.name}`).join(", ")}
              </p>
            </article>
          ))}
          {result.unmatched.length > 0 && (
            <div className="notice warning">
              <h3>{t("rankUnmatched")}</h3>
              {result.unmatched.map((u, i) => (
                <p key={i}>
                  {u.market}: {u.reason}
                </p>
              ))}
            </div>
          )}
          <details className="card">
            <summary>{t("rankSources")}</summary>
            <p>
              {t("source")}: {result.price_source}
            </p>
            <p>
              {result.rates.source} · {t("rankEffective")}:{" "}
              {result.rates.effective_from}
            </p>
            <p>
              {result.vehicle_rates.source} · {t("rankEffective")}:{" "}
              {result.vehicle_rates.effective_from}
            </p>
          </details>
          <a className="ranking-pool-link" href="#pools">
            {t("rankPool")}
          </a>
        </section>
      )}
    </>
  );
}
