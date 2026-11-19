import React, {
  useEffect,
  useState,
  createContext,
  useContext,
  useRef,
} from "react";
import { createRoot } from "react-dom/client";
import { api, money, quintals, indiaToday, marketRows } from "./lib";
import { translator, locales } from "./i18n";
import snapshot from "../../data/punjab_2026-09-07.json";
import card from "../../data/vehicle_rates.json";
import "./style.css";

const Context = createContext();
const useApp = () => useContext(Context);
const initialVehicles = () =>
  card.vehicles.map((v, i) => ({
    code: `vehicle-${i}`,
    name: v.name,
    capacity_quintals: String(v.capacity_quintals),
    base_cost_inr: String(v.base_cost_inr),
    per_km_inr: String(v.per_km_cost_inr),
  }));
const blankVehicle = () => ({
  code: `v-${crypto.randomUUID().slice(0, 8)}`,
  name: "",
  capacity_quintals: "",
  base_cost_inr: "",
  per_km_inr: "",
});
function Button({
  children,
  onClick,
  type = "button",
  secondary = false,
  ...rest
}) {
  const { busy } = useApp();
  return (
    <button
      type={type}
      onClick={onClick}
      className={secondary ? "secondary" : ""}
      {...rest}
      disabled={busy || rest.disabled}
    >
      {children}
    </button>
  );
}
function Field({ label, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input {...props} />
    </label>
  );
}
function Notice({ children, warning = false }) {
  return <div className={`notice ${warning ? "warning" : ""}`}>{children}</div>;
}
function Heading({ title, subtitle, action }) {
  return (
    <div className="heading">
      <div>
        <p className="eyebrow">MANDIWISE / PUNJAB</p>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
function App() {
  const [locale, setLocale] = useState(() => {
      try {
        return localStorage.getItem("mw-language") || "en";
      } catch {
        return "en";
      }
    }),
    [route, setRoute] = useState(location.hash.slice(1) || "home"),
    [user, setUser] = useState(null),
    [auth, setAuth] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const t = translator(locale),
    guard = useRef(false);
  useEffect(() => {
    const update = () => {
      setRoute(location.hash.slice(1) || "home");
      setError("");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir =
      locales.find((x) => x[0] === locale)?.[2] || "ltr";
    try {
      localStorage.setItem("mw-language", locale);
    } catch {}
  }, [locale]);
  useEffect(() => {
    api("/v1/me")
      .then(setUser)
      .catch((e) => {
        if (e.status !== 401) setError(e.message);
      });
  }, []);
  const run = async (fn) => {
    if (guard.current) return;
    guard.current = true;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      guard.current = false;
      setBusy(false);
    }
  };
  const go = (path) => {
    location.hash = path;
  };
  const requireUser = () => {
    if (user) return true;
    setAuth(true);
    return false;
  };
  const value = {
    t,
    user,
    setUser,
    run,
    busy,
    go,
    requireUser,
    setAuth,
    error,
  };
  const section = route.split("/")[0];
  return (
    <Context.Provider value={value}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <aside className="sidebar">
          <a className="brand" href="#home">
            <span className="brand-mark">
              m<span>↗</span>
            </span>
            <span>
              MandiWise<small>GROW TOGETHER</small>
            </span>
          </a>
          <div className="region">
            <span className="dot" />
            {t("punjab")}
          </div>
          <nav aria-label="Main navigation">
            {[
              ["home", "◫"],
              ["markets", "◈"],
              ["transport", "⇄"],
              ["pools", "♧"],
              ["mine", "▤"],
              ["help", "?"],
            ].map(([key, icon]) => (
              <a
                key={key}
                href={`#${key}`}
                aria-current={section === key ? "page" : undefined}
              >
                <span aria-hidden="true">{icon}</span>
                {t(key)}
              </a>
            ))}
          </nav>
          <div className="sidebar-note">
            <b>Built around farmers.</b>
            <p>
              Pool the vehicle.
              <br />
              Keep your produce yours.
            </p>
            <span>STUDENT PROJECT · LOCAL PILOT</span>
          </div>
        </aside>
        <div className="body">
          <header className="topbar">
            <span className="breadcrumb">
              {t(
                section in
                  {
                    home: 1,
                    markets: 1,
                    transport: 1,
                    pools: 1,
                    mine: 1,
                    help: 1,
                  }
                  ? section
                  : "home",
              )}
            </span>
            <div className="header-actions">
              <select
                aria-label="Language"
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
              >
                {locales.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
              {user ? (
                <>
                  <span className="user-name">{user.name}</span>
                  <Button
                    secondary
                    onClick={() =>
                      run(async () => {
                        await api("/portal/api/logout", {});
                        setUser(null);
                        go("home");
                      })
                    }
                  >
                    {t("logout")}
                  </Button>
                </>
              ) : (
                <Button onClick={() => setAuth(true)}>{t("login")}</Button>
              )}
            </div>
          </header>
          <main id="main" tabIndex="-1">
            {locale !== "en" && (
              <Notice warning>
                {t(["hi", "pa"].includes(locale) ? "translation" : "fallback")}
              </Notice>
            )}
            {error && (
              <div role="alert" className="error">
                {error}
                <button
                  type="button"
                  onClick={() => setError("")}
                  aria-label={t("close")}
                >
                  ×
                </button>
              </div>
            )}
            {busy && (
              <div className="progress" role="status">
                {t("working")}
              </div>
            )}
            {section === "home" ? (
              <Home />
            ) : section === "markets" ? (
              <Markets />
            ) : section === "transport" ? (
              <Transport />
            ) : section === "pools" || section === "mine" ? (
              <Pools key={`${route}:${user?.id || "guest"}`} route={route} />
            ) : (
              <Help />
            )}
          </main>
          <footer>
            {t("unit")}{" "}
            <span>MandiWise · Punjab · No payments or booking guarantees</span>
          </footer>
        </div>
      </div>
      {auth && <Auth close={() => setAuth(false)} />}
    </Context.Provider>
  );
}
function Home() {
  const { t, go } = useApp();
  return (
    <>
      <div className="hero">
        <div>
          <span className="pill">{t("workspace")}</span>
          <h1>{t("welcome")}</h1>
          <p>{t("intro")}</p>
          <div className="actions">
            <Button onClick={() => go("transport")}>{t("start")} ↗</Button>
            <Button secondary onClick={() => go("pools")}>
              {t("browse")}
            </Button>
          </div>
        </div>
        <div className="journey-art" aria-hidden="true">
          <div className="sun" />
          <div className="hill one" />
          <div className="hill two" />
          <div className="road" />
          <div className="truck">
            ▰<span>●　●</span>
          </div>
          <div className="art-label">
            YOUR NEXT JOURNEY
            <br />
            <b>Better, together.</b>
          </div>
        </div>
      </div>
      <div className="stats">
        <div>
          <span>FOCUS REGION</span>
          <strong>Punjab</strong>
          <small>{t("punjab")}</small>
        </div>
        <div>
          <span>PRICE SNAPSHOTS</span>
          <strong>
            02 <small>days captured</small>
          </strong>
          <small>04 & 07 Sep 2026 · not live</small>
        </div>
        <div>
          <span>YOUR PRODUCE</span>
          <strong>Always yours</strong>
          <small>Shared transport, separate lots</small>
        </div>
      </div>
      <div className="heading">
        <h2>{t("how")}</h2>
        <span className="muted">From your farm to the right journey.</span>
      </div>
      <div className="feature-grid">
        {[
          [
            "markets",
            "01",
            t("step1"),
            "View actual source observations, dates and reported price ranges.",
          ],
          [
            "transport",
            "02",
            t("step2"),
            "Compare whole-vehicle choices and see exactly how each share is calculated.",
          ],
          [
            "pools",
            "03",
            t("step3"),
            "Create a trip, review requests and coordinate with approved members.",
          ],
        ].map(([path, n, title, text]) => (
          <a className="feature card" key={path} href={`#${path}`}>
            <span className="number">{n}</span>
            <h2>{title}</h2>
            <p>{text}</p>
            <span className="arrow">↗</span>
          </a>
        ))}
      </div>
      <Notice warning>
        {t("historical")}. {t("netNotice")}
      </Notice>
    </>
  );
}
function Markets() {
  const { t } = useApp();
  const [crop, setCrop] = useState("Potato"),
    [district, setDistrict] = useState(""),
    [search, setSearch] = useState("");
  const rows = marketRows(snapshot).filter(
    (r) =>
      (!crop || r.commodity === crop) &&
      (!district || r.district === district) &&
      r.market.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <Heading
        title={t("markets")}
        subtitle="Dated observations. Transparent sources. No hidden assumptions."
      />
      <Notice warning>
        <b>{t("historical")}</b>
        <p>{t("snapshotNotice")}</p>
      </Notice>
      <div className="filters card">
        <label className="field">
          <span>{t("crop")}</span>
          <select value={crop} onChange={(e) => setCrop(e.target.value)}>
            <option value="">{t("all")}</option>
            {[...new Set(snapshot.map((r) => r.commodity))].sort().map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("district")}</span>
          <select
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
          >
            <option value="">{t("all")}</option>
            {[...new Set(snapshot.map((r) => r.district))].sort().map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <Field
          label={t("search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Patiala APMC"
        />
      </div>
      <div className="heading">
        <h2>{rows.length} observations</h2>
        <span className="muted">
          {t("source")}: AGMARKNET / data.gov.in · 07 Sep 2026
        </span>
      </div>
      <div className="market-grid">
        {rows.map((r, i) => (
          <article
            className="card market"
            key={`${r.market}-${r.commodity}-${r.variety}-${i}`}
          >
            <span className="tag">{r.district}</span>
            <h2>{r.market}</h2>
            <p className="muted">
              {r.commodity} · {r.variety} · {r.grade}
            </p>
            <p className="price">{money(r.modal_price)}</p>
            <span className="muted">{t("modal")}</span>
            <hr />
            <dl>
              <dt>{t("range")}</dt>
              <dd>
                {money(r.min_price)} – {money(r.max_price)}
              </dd>
              <dt>{t("date")}</dt>
              <dd>{r.arrival_date}</dd>
            </dl>
          </article>
        ))}
      </div>
      {!rows.length && <div className="empty">{t("empty")}</div>}
      <div className="card muted">
        <h2>{t("netTitle")}</h2>
        <p>{t("netNotice")}</p>
        <p>
          12 rows below the project’s ₹50/quintal screening floor are excluded
          from this snapshot view. Raw data remains unchanged. This is not a
          quality guarantee.
        </p>
      </div>
    </>
  );
}
function VehicleEditor({ vehicles, setVehicles }) {
  const { t } = useApp();
  return (
    <section className="card">
      <div className="heading">
        <h2>{t("vehicles")}</h2>
        <Button
          secondary
          disabled={vehicles.length >= 12}
          onClick={() => setVehicles([...vehicles, blankVehicle()])}
        >
          + {t("addVehicle")}
        </Button>
      </div>
      {vehicles.map((v, i) => (
        <div className="vehicle-row" key={v.code}>
          {[
            ["name", "vehicle", "text"],
            ["capacity_quintals", "capacity", "number"],
            ["base_cost_inr", "base", "number"],
            ["per_km_inr", "perKm", "number"],
          ].map(([key, label, type]) => (
            <Field
              key={key}
              label={t(label)}
              type={type}
              required
              value={v[key]}
              min={key === "capacity_quintals" ? ".01" : 0}
              max={key === "capacity_quintals" ? 1000 : 1000000}
              step=".01"
              maxLength={160}
              onChange={(e) =>
                setVehicles(
                  vehicles.map((x, j) =>
                    j === i ? { ...x, [key]: e.target.value } : x,
                  ),
                )
              }
            />
          ))}
          <Button
            secondary
            disabled={vehicles.length === 1}
            onClick={() => setVehicles(vehicles.filter((_, j) => j !== i))}
          >
            {t("remove")}
          </Button>
        </div>
      ))}
    </section>
  );
}
function Transport() {
  const { t, run } = useApp();
  const [distance, setDistance] = useState("60"),
    [farmers, setFarmers] = useState([
      { name: "Farmer 1", quantity_quintals: "40" },
      { name: "Farmer 2", quantity_quintals: "40" },
    ]),
    [vehicles, setVehicles] = useState(initialVehicles),
    [result, setResult] = useState(null);
  const change = (setter, value) => {
    setter(value);
    setResult(null);
  };
  return (
    <>
      <Heading
        title={t("transport")}
        subtitle="Choose the load. Check every rupee. Share the journey."
      />
      <Notice warning>{t("rateNotice")}</Notice>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(async () =>
            setResult(
              await api("/demo/calculate", {
                distance_km: distance,
                farmers,
                vehicles,
              }),
            ),
          );
        }}
      >
        <section className="card">
          <Field
            label={t("distance")}
            type="number"
            min=".001"
            max="2000"
            step=".001"
            required
            value={distance}
            onChange={(e) => change(setDistance, e.target.value)}
          />
          <div className="heading">
            <h2>{t("yourLot")}</h2>
            <Button
              secondary
              disabled={farmers.length >= 8}
              onClick={() =>
                change(setFarmers, [
                  ...farmers,
                  { name: "", quantity_quintals: "" },
                ])
              }
            >
              + {t("addFarmer")}
            </Button>
          </div>
          {farmers.map((f, i) => (
            <div className="form-row" key={i}>
              <Field
                label={t("farmer")}
                required
                maxLength={160}
                value={f.name}
                onChange={(e) =>
                  change(
                    setFarmers,
                    farmers.map((x, j) =>
                      i === j ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
              />
              <Field
                label={t("quantity")}
                type="number"
                required
                min=".01"
                max="1000"
                step=".01"
                value={f.quantity_quintals}
                onChange={(e) =>
                  change(
                    setFarmers,
                    farmers.map((x, j) =>
                      i === j ? { ...x, quantity_quintals: e.target.value } : x,
                    ),
                  )
                }
              />
              <Button
                secondary
                disabled={farmers.length === 1}
                onClick={() =>
                  change(
                    setFarmers,
                    farmers.filter((_, j) => j !== i),
                  )
                }
              >
                {t("remove")}
              </Button>
            </div>
          ))}
        </section>
        <VehicleEditor
          vehicles={vehicles}
          setVehicles={(v) => change(setVehicles, v)}
        />
        <Button type="submit">{t("calculate")} ↗</Button>
      </form>
      {result && (
        <div aria-live="polite" className="result">
          <div className="stats">
            <div>
              <span>{t("solo")}</span>
              <strong>{money(result.individual_total_inr)}</strong>
            </div>
            <div>
              <span>{t("pooled")}</span>
              <strong>{money(result.cost_inr)}</strong>
            </div>
            <div>
              <span>{t("saving")}</span>
              <strong>{money(result.total_savings_inr)}</strong>
            </div>
          </div>
          <Quote result={result} />
        </div>
      )}
    </>
  );
}
function Quote({ result }) {
  const { t } = useApp();
  return (
    <section className="card">
      <h2>
        {t("estimate")} · {money(result.cost_inr)}
      </h2>
      {result.all_participants_benefit === false && (
        <Notice warning>{t("fairWarning")}</Notice>
      )}
      <p>
        {t("fleet")}:{" "}
        {result.vehicles.map((v) => `${v.count} × ${v.code}`).join(", ")} ·{" "}
        {t("unused")}: {quintals(result.unused_capacity_kg)} q
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {["farmer", "quantity", "individual", "share", "saved"].map(
                (x) => (
                  <th key={x}>{t(x)}</th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {result.participants?.map((p, i) => (
              <tr key={p.participant_id}>
                <td>{p.name || `${t("farmer")} ${i + 1}`}</td>
                <td>{quintals(p.quantity_kg)} q</td>
                <td>{money(p.individual_cost_inr)}</td>
                <td>{money(p.share_inr)}</td>
                <td
                  className={p.benefits_from_pooling ? "positive" : "negative"}
                >
                  {money(p.savings_inr)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Share = your quintals ÷ group quintals × transport total. The backend
        distributes remaining paise so shares add up exactly.
      </p>
      {result.warnings?.map((w) => (
        <p className="muted" key={w}>
          {w}
        </p>
      ))}
    </section>
  );
}
function Auth({ close }) {
  const { t, run, setUser, busy, error } = useApp();
  const [register, setRegister] = useState(false);
  const dialog = useRef(null);
  useEffect(() => {
    dialog.current.showModal();
    const el = dialog.current;
    return () => el.close();
  }, []);
  return (
    <dialog ref={dialog} onCancel={close}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const body = Object.fromEntries(new FormData(e.currentTarget));
          run(async () => {
            setUser(
              await api(`/portal/api/${register ? "register" : "login"}`, body),
            );
            close();
          });
        }}
      >
        <div className="heading">
          <h2>{t(register ? "register" : "login")}</h2>
          <button type="button" onClick={close} aria-label={t("close")}>
            ×
          </button>
        </div>
        {register && (
          <>
            <Field label={t("name")} name="name" required maxLength={160} />
            <Field
              label={t("village")}
              name="village"
              required
              maxLength={160}
            />
          </>
        )}
        <Field
          label={t("username")}
          name="username"
          required
          pattern="[a-z0-9_]{3,40}"
          autoComplete="username"
        />
        <Field
          label={t("password")}
          name="password"
          required
          type="password"
          minLength={register ? 15 : 1}
          maxLength={128}
          autoComplete={register ? "new-password" : "current-password"}
        />
        <p className="muted">{t("passwordHint")}</p>
        <Button type="submit">
          {busy ? t("working") : t(register ? "register" : "login")}
        </Button>
        <Button secondary onClick={() => setRegister(!register)}>
          {t(register ? "login" : "register")}
        </Button>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </form>
    </dialog>
  );
}
function LotFields() {
  const { t } = useApp();
  return (
    <div className="grid2">
      <Field
        label={t("quantity")}
        name="quantity_quintals"
        type="number"
        required
        min=".01"
        max="1000"
        step=".01"
      />
      <Field label={t("variety")} name="variety" required maxLength={160} />
      <Field label={t("grade")} name="grade" required maxLength={160} />
      <Field label={t("condition")} name="condition" required maxLength={500} />
    </div>
  );
}
function Pools({ route }) {
  const { t, user, run, go, requireUser } = useApp();
  const mine = route === "mine";
  const [rows, setRows] = useState([]),
    [search, setSearch] = useState(""),
    [day, setDay] = useState(""),
    [loading, setLoading] = useState(false),
    [more, setMore] = useState(false),
    [loadError, setLoadError] = useState("");
  const id = route.split("/")[1];
  async function load(append = false) {
    setLoading(true);
    setLoadError("");
    try {
      const params = new URLSearchParams({
        search,
        limit: "30",
        offset: String(append ? rows.length : 0),
      });
      if (day) params.set("travel_date", day);
      const data = await api(
        mine ? "/portal/api/mine" : `/portal/api/trips?${params}`,
      );
      setRows(append ? [...rows, ...data] : data);
      setMore(!mine && data.length === 30);
    } catch (e) {
      setLoadError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (!id && (!mine || user)) load();
  }, [route, user?.id]);
  if (id === "new")
    return user ? (
      <NewTrip />
    ) : (
      <Notice>
        {t("authNeeded")} <Button onClick={requireUser}>{t("login")}</Button>
      </Notice>
    );
  if (id) return <Trip id={id} />;
  if (mine && !user)
    return (
      <Notice>
        {t("authNeeded")} <Button onClick={requireUser}>{t("login")}</Button>
      </Notice>
    );
  return (
    <>
      <Heading
        title={t(mine ? "mine" : "trips")}
        subtitle={t("tripIntro")}
        action={
          <Button
            onClick={() => {
              if (requireUser()) go("pools/new");
            }}
          >
            + {t("newTrip")}
          </Button>
        }
      />
      <Notice>{t("accountNotice")}</Notice>
      {!mine && (
        <form
          className="filters card"
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
        >
          <Field
            label={t("search")}
            placeholder="Patiala, potato…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Field
            label={t("travel")}
            type="date"
            value={day}
            onChange={(e) => setDay(e.target.value)}
          />
          <Button type="submit" disabled={loading}>
            {t("search")}
          </Button>
        </form>
      )}
      <div className="heading">
        <span className="muted">{rows.length} trips</span>
        <Button secondary disabled={loading} onClick={() => load()}>
          {t("refresh")}
        </Button>
      </div>
      {loadError && (
        <div className="error" role="alert">
          {loadError}
        </div>
      )}
      {loading && <p role="status">{t("loading")}</p>}
      <div className="market-grid">
        {rows.map((p) => (
          <article key={p.id} className="card">
            <div className="between">
              <span className="tag">{p.state}</span>
              <span>{p.travel_date}</span>
            </div>
            <h2>
              {p.origin} → {p.destination}
            </h2>
            <p>
              {p.commodity} · {p.distance_km} km
            </p>
            <p className="muted">
              {t("organizer")}: {p.organizer}
            </p>
            <p>
              {quintals(p.approved_quantity_kg)} / {quintals(p.max_quantity_kg)}{" "}
              q · {p.farmer_count} farmers
            </p>
            <progress
              aria-label={t("load")}
              value={p.approved_quantity_kg}
              max={p.max_quantity_kg}
            />
            <Button secondary onClick={() => go(`pools/${p.id}`)}>
              {t("open")} ↗
            </Button>
          </article>
        ))}
      </div>
      {!rows.length && !loading && !loadError && (
        <div className="empty">
          <h2>{t("noTrips")}</h2>
          <p>{t("tripIntro")}</p>
        </div>
      )}
      {more && (
        <Button disabled={loading} onClick={() => load(true)}>
          {t("more")}
        </Button>
      )}
    </>
  );
}
function NewTrip() {
  const { t, run, go } = useApp();
  const [vehicles, setVehicles] = useState(() => [blankVehicle()]);
  return (
    <>
      <Heading title={t("newTrip")} subtitle={t("tripIntro")} />
      <Notice warning>{t("unverified")}</Notice>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.currentTarget));
          const lot = Object.fromEntries(
            ["quantity_quintals", "variety", "grade", "condition"].map((k) => [
              k,
              f[k],
            ]),
          );
          const body = Object.fromEntries(
            [
              "origin",
              "destination",
              "district",
              "travel_date",
              "commodity",
              "pickup_description",
              "distance_km",
              "max_quantity_quintals",
            ].map((k) => [k, f[k]]),
          );
          run(async () => {
            const trip = await api("/portal/api/trips", {
              ...body,
              state: "Punjab",
              lot,
              vehicles,
            });
            go(`pools/${trip.id}`);
          });
        }}
      >
        <section className="card">
          <h2>01 / {t("travel")}</h2>
          <div className="grid2">
            {[
              ["origin", "origin"],
              ["destination", "destination"],
              ["district", "district"],
              ["commodity", "crop"],
              ["pickup_description", "pickup"],
            ].map(([name, label]) => (
              <Field
                key={name}
                label={t(label)}
                name={name}
                required
                maxLength={name === "pickup_description" ? 500 : 160}
              />
            ))}
            <Field
              label={t("travel")}
              name="travel_date"
              type="date"
              min={indiaToday()}
              required
            />
            <Field
              label={t("distance")}
              name="distance_km"
              type="number"
              min=".001"
              max="2000"
              step=".001"
              required
            />
            <Field
              label={t("maxLoad")}
              name="max_quantity_quintals"
              type="number"
              min=".01"
              max="1000"
              step=".01"
              required
            />
          </div>
          <p className="muted">
            {t("state")}: Punjab. Pickup and destination must currently share
            the entered district; cross-district trip metadata needs a backend
            change.
          </p>
        </section>
        <section className="card">
          <h2>02 / {t("yourLot")}</h2>
          <LotFields />
        </section>
        <VehicleEditor vehicles={vehicles} setVehicles={setVehicles} />
        <label className="checkbox">
          <input type="checkbox" required />
          {t("confirm")}
        </label>
        <p className="muted">{t("privacy")}</p>
        <div className="actions">
          <Button type="submit">{t("create")}</Button>
          <Button secondary onClick={() => go("pools")}>
            {t("cancel")}
          </Button>
        </div>
      </form>
    </>
  );
}
function Trip({ id }) {
  const { t, user, run, go, requireUser } = useApp();
  const [trip, setTrip] = useState(null),
    [view, setView] = useState(null),
    [quote, setQuote] = useState(null),
    [messages, setMessages] = useState([]),
    [error, setError] = useState(""),
    [chatError, setChatError] = useState("");
  const reload = async () => {
    const data = await api(`/portal/api/trips/${id}`);
    setTrip(data);
    setQuote(null);
    if (user) {
      const w = await api(`/portal/api/trips/${id}/workspace`);
      setView(w);
    } else setView(null);
  };
  useEffect(() => {
    reload().catch((e) => setError(e.message));
  }, [id, user?.id]);
  const owner = !!user && trip?.organizer_id === user.id;
  const self = view?.members?.find((m) => m.user_id === user?.id);
  const canChat = owner || self?.status === "APPROVED";
  const open = trip?.state === "OPEN";
  const loadChat = async () => {
    try {
      setMessages(await api(`/portal/api/trips/${id}/messages`));
      setChatError("");
    } catch (e) {
      setChatError(e.message);
    }
  };
  useEffect(() => {
    if (canChat) loadChat();
  }, [id, canChat]);
  const action = async (path, body) => {
    try {
      await api(`/v1/pools/${id}/${path}`, body);
    } finally {
      await reload();
    }
  };
  if (error)
    return (
      <div className="error">
        {error}{" "}
        <Button
          secondary
          onClick={() =>
            run(async () => {
              setError("");
              await reload();
            })
          }
        >
          {t("retry")}
        </Button>
      </div>
    );
  if (!trip) return <p role="status">{t("loading")}</p>;
  return (
    <>
      <Button secondary onClick={() => go("pools")}>
        ← {t("back")}
      </Button>
      <Heading
        title={`${trip.origin} → ${trip.destination}`}
        subtitle={`${trip.commodity} · ${trip.travel_date} · ${trip.distance_km} km`}
        action={<span className="tag">{trip.state}</span>}
      />
      <Notice warning>{t("unverified")}</Notice>
      <div className="detail-grid">
        <section className="card">
          <h2>{t("pickup")}</h2>
          <p>{trip.pickup_description}</p>
          <dl>
            <dt>{t("organizer")}</dt>
            <dd>{trip.organizer}</dd>
            <dt>{t("load")}</dt>
            <dd>
              {quintals(trip.approved_quantity_kg)} /{" "}
              {quintals(trip.max_quantity_kg)} q
            </dd>
            <dt>{t("status")}</dt>
            <dd>{self?.status || "Not joined"}</dd>
          </dl>
          <Button secondary onClick={() => run(reload)}>
            {t("refresh")}
          </Button>
        </section>
        <section className="card">
          <h2>{t("vehicles")}</h2>
          {trip.vehicles.map((v) => (
            <p key={v.code}>
              <b>{v.name || v.code}</b> · {v.capacity_quintals} q<br />
              {money(v.base_cost_inr)} + {money(v.per_km_inr)} / km
            </p>
          ))}
        </section>
      </div>
      {!user && <Button onClick={requireUser}>{t("login")}</Button>}
      {user &&
        open &&
        (!self || ["WITHDRAWN", "REJECTED"].includes(self.status)) && (
          <form
            className="card"
            onSubmit={(e) => {
              e.preventDefault();
              const body = Object.fromEntries(new FormData(e.currentTarget));
              run(() => action("join", body));
            }}
          >
            <h2>{t("join")}</h2>
            <LotFields />
            <Button type="submit">{t("join")}</Button>
          </form>
        )}
      {user &&
        self &&
        open &&
        ["APPROVED", "PENDING"].includes(self.status) && (
          <Button
            secondary
            onClick={() =>
              run(() => action("withdraw", { expected_version: view.version }))
            }
          >
            {t("withdraw")}
          </Button>
        )}
      {view?.members?.length > 0 && (
        <section className="card">
          <h2>{t("members")}</h2>
          {view.members.map((m) => (
            <div className="member" key={m.id}>
              <div>
                <b>{m.name || t("farmer")}</b>
                <p>
                  {quintals(m.quantity_kg)} q · {m.variety} · {m.grade}
                </p>
                <small>{m.condition}</small>
              </div>
              <span className="tag">{m.status}</span>
              {owner && open && m.status === "PENDING" && (
                <div className="actions">
                  {["APPROVED", "REJECTED"].map((decision) => (
                    <Button
                      key={decision}
                      secondary
                      onClick={() =>
                        run(() =>
                          action(`members/${m.id}/review`, {
                            expected_version: view.version,
                            decision,
                          }),
                        )
                      }
                    >
                      {t(decision === "APPROVED" ? "approve" : "reject")}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </section>
      )}
      {user && (owner || self) && (
        <>
          <Button
            secondary
            onClick={() =>
              run(async () => setQuote(await api(`/v1/pools/${id}/quote`, {})))
            }
          >
            {t("quote")}
          </Button>
          {(quote || view?.locked_quote) && (
            <Quote result={quote || view.locked_quote} />
          )}
        </>
      )}
      {owner && view && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            const f = Object.fromEntries(new FormData(e.currentTarget));
            const target = e.nativeEvent.submitter.value;
            const body = {
              target,
              expected_version: view.version,
              ...(f.note ? { note: f.note } : {}),
              ...(f.transport_reference
                ? { transport_reference: f.transport_reference }
                : {}),
            };
            run(() => action("transition", body));
          }}
        >
          <h2>Trip management</h2>
          {trip.state === "LOCKED" && (
            <Field
              label={t("reference")}
              name="transport_reference"
              maxLength={300}
            />
          )}
          <Field label={t("note")} name="note" maxLength={500} />
          <div className="actions">
            {(
              {
                OPEN: [
                  ["LOCKED", "lock"],
                  ["CANCELLED", "cancelTrip"],
                ],
                LOCKED: [
                  ["DISPATCHED", "dispatch"],
                  ["CANCELLED", "cancelTrip"],
                ],
                DISPATCHED: [["SETTLED", "settle"]],
              }[trip.state] || []
            ).map(([target, label]) => (
              <Button key={target} type="submit" value={target}>
                {t(label)}
              </Button>
            ))}
          </div>
          <p className="muted">
            Review all pending requests before locking. Dispatch requires a
            transport reference; completion/cancellation requires a note.
          </p>
        </form>
      )}
      <section className="card">
        <div className="heading">
          <h2>{t("chat")}</h2>
          {canChat && (
            <Button secondary onClick={() => run(loadChat)}>
              {t("refresh")}
            </Button>
          )}
        </div>
        {!canChat ? (
          <p>{t("chatGate")}</p>
        ) : (
          <>
            {chatError && <p role="alert">{chatError}</p>}
            <div className="messages" aria-live="polite">
              {!messages.length && <p className="muted">{t("noMessages")}</p>}
              {messages.map((m) => (
                <article key={m.id}>
                  <strong>{m.name}</strong>
                  <p>{m.body}</p>
                  <time>{new Date(m.created_at).toLocaleString("en-IN")}</time>
                </article>
              ))}
            </div>
            {["SETTLED", "CANCELLED"].includes(trip.state) ? (
              <p>{t("closedChat")}</p>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget;
                  const body = Object.fromEntries(new FormData(form));
                  run(async () => {
                    await api(`/portal/api/trips/${id}/messages`, body);
                    form.reset();
                    await loadChat();
                  });
                }}
              >
                <Field
                  label={t("message")}
                  name="body"
                  required
                  maxLength={1000}
                />
                <Button type="submit">{t("send")}</Button>
              </form>
            )}
          </>
        )}
      </section>
    </>
  );
}
function Help() {
  const { t, user } = useApp();
  return (
    <>
      <Heading
        title={t("help")}
        subtitle="What is working, what the numbers mean, and what comes next."
      />
      <div className="grid2">
        <section className="card">
          <h2>{t("implemented")}</h2>
          <ul>
            <li>Backend-calculated vehicle combinations and cost shares.</li>
            <li>Saved accounts, trip discovery and membership approval.</li>
            <li>Pool lifecycle, private shares and approved-member chat.</li>
            <li>Read-only view of committed Punjab price observations.</li>
          </ul>
        </section>
        <section className="card">
          <h2>{t("pending")}</h2>
          <ul>
            <li>Verified net-return ranking API and price-derived ranges.</li>
            <li>Scheduled fresh prices, sourced fees and road distances.</li>
            <li>
              Current liquidity signal: two snapshot days are insufficient.
            </li>
            <li>
              Human-reviewed Hindi/Punjabi translations and public hosting.
            </li>
          </ul>
        </section>
        <section className="card">
          <h2>{t("health")}</h2>
          <p>
            Historical CEDA: 16,907 rows, seven Patiala-district mandis, eight
            crops, October 2023–October 2025. Grades are missing.
          </p>
          <p>
            AGMARKNET snapshots: 836 rows over 4 and 7 September 2026, 50 market
            names. This frontend displays the latter snapshot with basic price
            screening.
          </p>
          <p>
            Historical observations are not today's selling prices. No demand or
            price forecast is offered.
          </p>
        </section>
        <section className="card">
          <h2>{t("account")}</h2>
          {user ? (
            <p>
              {user.name} · {t("role")}: {user.role || "farmer account"}
            </p>
          ) : (
            <p>{t("login")}</p>
          )}
          <p>{t("accountNotice")}</p>
          <p>{t("privacy")}</p>
        </section>
      </div>
      <Notice warning>
        Never use the default vehicle rates as a real quotation. This local
        prototype does not book a driver, collect payment or verify farmer
        identities.
      </Notice>
      <a href="http://127.0.0.1:8001/demo" target="_blank" rel="noreferrer">
        Open the original calculator ↗
      </a>
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
