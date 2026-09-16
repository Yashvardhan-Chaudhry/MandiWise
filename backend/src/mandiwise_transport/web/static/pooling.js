const $ = (id) => document.getElementById(id),
  money = (n) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
    }).format(Number(n)),
  q = (n) => Number((n / 100).toFixed(2));
let user = null,
  registering = false,
  mode = "discover",
  offset = 0,
  active = null,
  view = null,
  chatAllowed = false;
const node = (tag, text, cls) => {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
const button = (text, fn, cls = "smallbtn") => {
  const b = node("button", text, cls);
  b.type = "button";
  b.onclick = () => run(fn);
  return b;
};
async function api(path, body) {
  const r = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      "X-MandiWise-Request": "portal",
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let data = await r.json();
  if (!r.ok) {
    let msg = data.error?.message || data.detail || "Request failed";
    if (Array.isArray(msg))
      msg = msg
        .map((e) => e.loc.slice(1).join(" → ") + ": " + e.msg)
        .join("\n");
    throw new Error(msg);
  }
  return data;
}
async function run(fn) {
  $("error").hidden = true;
  try {
    await fn();
  } catch (e) {
    $("error").textContent = e.message;
    $("error").hidden = false;
    $("error").scrollIntoView({ block: "start", behavior: "smooth" });
  }
}
function show(section) {
  ["browse", "post", "detail"].forEach((id) => ($(id).hidden = id !== section));
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function toast(text) {
  $("notice").className = "success";
  $("notice").textContent = text;
  $("notice").hidden = false;
  setTimeout(() => ($("notice").hidden = true), 6000);
}
function needUser() {
  if (user) return true;
  $("auth").showModal();
  return false;
}
function identity() {
  const root = $("identity");
  root.replaceChildren();
  if (user) {
    root.append(
      node("span", "Hello, " + user.name + " "),
      button("Sign out", async () => {
        await api("/portal/api/logout", {});
        user = null;
        identity();
        show("browse");
        mode = "discover";
        await list();
      }),
    );
  } else
    root.append(
      button("Sign in / Create account", () => {
        $("auth").showModal();
      }),
    );
}
function lotForm(root, prefix) {
  [
    ["quantity", "Your load (quintals)", "number"],
    ["variety", "Variety", "text"],
    ["grade", "Grade / quality description", "text"],
    ["condition", "Condition / packing notes", "text"],
  ].forEach(([key, title, type]) => {
    const label = node("label", title),
      input = node("input");
    input.id = prefix + "-" + key;
    label.htmlFor = input.id;
    input.type = type;
    input.required = true;
    input.maxLength = key === "condition" ? 500 : 160;
    if (type === "number") {
      input.min = 0.01;
      input.max = 1000;
      input.step = 0.01;
    }
    root.append(label, input);
  });
}
function lot(prefix) {
  return {
    quantity_quintals: $(prefix + "-quantity").value,
    variety: $(prefix + "-variety").value,
    grade: $(prefix + "-grade").value,
    condition: $(prefix + "-condition").value,
  };
}
lotForm($("own-lot"), "own");
const editor = new VehicleEditor($("portal-vehicles"), $("portal-add-vehicle"));
const today = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Kolkata",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());
$("p-date").min = today;
async function list(append = false) {
  if (!append) {
    offset = 0;
    $("trips").replaceChildren(node("p", "Loading trips…"));
  }
  const params = new URLSearchParams({
    search: $("search").value,
    offset,
    limit: 30,
  });
  if ($("filter-date").value) params.set("travel_date", $("filter-date").value);
  const rows = await api(
    mode === "mine" ? "/portal/api/mine" : "/portal/api/trips?" + params,
  );
  if (!append) $("trips").replaceChildren();
  $("search-form").hidden = mode === "mine";
  $("list-heading").textContent =
    mode === "mine" ? "My trips & requests" : "Open pooling trips";
  $("discover").className = mode === "discover" ? "primary" : "";
  $("mine").className = mode === "mine" ? "primary" : "";
  if (!rows.length && !append) {
    const empty = node("div", undefined, "empty");
    empty.append(
      node(
        "h3",
        mode === "mine"
          ? "Your pooling journey starts here"
          : "No matching trips yet",
      ),
      node(
        "p",
        mode === "mine"
          ? "Post a trip or request to join one. Your trips and requests will appear here."
          : "Try a different search, or post your own trip so other farmers can find you.",
      ),
    );
    $("trips").append(empty);
  }
  rows.forEach((t) => {
    const c = node("article", undefined, "card trip");
    c.append(
      node("span", t.state + " · " + t.travel_date, "badge"),
      node("h3", t.origin + " → " + t.destination),
      node("p", t.commodity + " · " + t.district + ", " + t.state_name),
      node("p", "Organized by " + t.organizer, "help"),
      node(
        "p",
        t.farmer_count +
          " approved farmer(s) · " +
          q(t.approved_quantity_kg) +
          " / " +
          q(t.max_quantity_kg) +
          " quintals",
      ),
      button("View trip & connect →", () => openTrip(t.id), "primary"),
    );
    $("trips").append(c);
  });
  offset += rows.length;
  $("more").hidden = mode === "mine" || rows.length < 30;
  $("count").textContent = offset ? offset + " trip(s) shown" : "";
}
async function openTrip(id) {
  active = await api("/portal/api/trips/" + id);
  view = user ? await api("/portal/api/trips/" + id + "/workspace") : null;
  show("detail");
  $("trip-heading").replaceChildren(
    node("span", active.state + " · " + active.travel_date, "badge"),
    node("h1", active.origin + " → " + active.destination),
  );
  const info = $("trip-info");
  info.replaceChildren(
    node("h2", "The shared plan"),
    node(
      "p",
      active.commodity + " · " + active.district + ", " + active.state_name,
    ),
    node("p", "Meeting point: " + active.pickup_description),
    node("p", "Organizer: " + active.organizer),
    node(
      "p",
      active.distance_km +
        " km · " +
        q(active.approved_quantity_kg) +
        " / " +
        q(active.max_quantity_kg) +
        " quintals approved",
    ),
    node("p", active.rates_notice, "notice"),
  );
  active.vehicles.forEach((v) =>
    info.append(
      node(
        "p",
        (v.name || v.code) +
          " · " +
          v.capacity_quintals +
          " q capacity · " +
          money(v.base_cost_inr) +
          " fixed + " +
          money(v.per_km_inr) +
          "/km",
        "help",
      ),
    ),
  );
  const owner = user?.id === active.organizer_id,
    own = view?.members.find((m) => m.user_id === user?.id),
    open = active.state === "OPEN" && active.travel_date >= today;
  const members = $("membership");
  members.replaceChildren(
    node("h2", owner ? "Farmers & join requests" : "Your place in this group"),
  );
  if (!user)
    members.append(
      node("p", "Sign in to send a join request."),
      button("Sign in to join", () => needUser(), "primary"),
    );
  else if (!own || ["REJECTED", "WITHDRAWN"].includes(own.status)) {
    if (own) members.append(node("p", "Your previous request: " + own.status));
    if (open) {
      const form = node("form");
      lotForm(form, "join");
      form.append(
        node(
          "p",
          "Only the organizer sees your lot declaration until approval. Requesting a place does not reserve a vehicle.",
          "help",
        ),
      );
      const submit = node("button", "Request to join", "primary smallbtn");
      form.append(submit);
      form.onsubmit = (e) => {
        e.preventDefault();
        run(async () => {
          submit.disabled = true;
          try {
            await api("/v1/pools/" + id + "/join", lot("join"));
            toast("Request sent. The organizer needs to approve your load.");
            await openTrip(id);
          } finally {
            submit.disabled = false;
          }
        });
      };
      members.append(form);
    } else members.append(node("p", "This trip is closed to new requests."));
  } else {
    members.append(
      node(
        "p",
        "Your request: " +
          own.status +
          " · " +
          q(own.quantity_kg) +
          " quintals",
        "badge",
      ),
    );
    if (own.status === "PENDING")
      members.append(
        node(
          "p",
          "Waiting for the organizer. Refresh this trip to check for approval.",
        ),
      );
    if (open && ["PENDING", "APPROVED"].includes(own.status))
      members.append(
        button("Withdraw my load", async () => {
          if (confirm("Withdraw your load from this trip?")) {
            await api("/v1/pools/" + id + "/withdraw", {
              expected_version: view.version,
            });
            await openTrip(id);
          }
        }),
      );
  }
  if (owner) {
    view.members
      .filter((m) => m.user_id !== user.id)
      .forEach((m) => {
        const row = node("div", undefined, "member");
        row.append(
          node("strong", m.name + " · " + m.status),
          node(
            "p",
            q(m.quantity_kg) +
              " q · " +
              m.variety +
              " · " +
              m.grade +
              " · " +
              m.condition,
          ),
        );
        if (m.status === "PENDING" && open)
          ["APPROVED", "REJECTED"].forEach((decision) =>
            row.append(
              button(
                decision === "APPROVED" ? "Approve load" : "Reject request",
                async () => {
                  await api(
                    "/v1/pools/" + id + "/members/" + m.id + "/review",
                    { decision, expected_version: view.version },
                  );
                  await openTrip(id);
                },
              ),
            ),
          );
        members.append(row);
      });
    if (view.members.length <= 1)
      members.append(
        node(
          "p",
          "No other join requests yet. Other farmers can find this trip in “Find a trip”.",
          "help",
        ),
      );
  }
  $("manage").hidden = !owner;
  $("manage-controls").replaceChildren();
  if (owner) {
    if (open)
      $("manage-controls").append(
        button(
          "Lock group & cost split",
          () => transition("LOCKED"),
          "primary",
        ),
      );
    if (active.state === "LOCKED")
      $("manage-controls").append(
        button("Mark dispatched", () => transition("DISPATCHED"), "primary"),
      );
    if (active.state === "DISPATCHED")
      $("manage-controls").append(
        button("Mark trip settled", () => transition("SETTLED"), "primary"),
      );
    if (["OPEN", "LOCKED"].includes(active.state))
      $("manage-controls").append(
        button("Cancel trip", () => transition("CANCELLED")),
      );
  }
  const qc = $("quote-content");
  qc.replaceChildren();
  if (owner || own?.status === "APPROVED") {
    try {
      const estimate = await api("/v1/pools/" + id + "/quote", {});
      const metric = node("div", undefined, "metric");
      metric.append(
        node(
          "span",
          "Whole group · " +
            (active.state === "OPEN" ? "current estimate" : "locked estimate"),
        ),
        node("strong", money(estimate.cost_inr)),
      );
      qc.append(
        metric,
        node(
          "p",
          estimate.vehicles
            .map(
              (v) =>
                v.count +
                " × " +
                (active.vehicles.find((x) => x.code === v.code)?.name ||
                  v.code),
            )
            .join(" + "),
        ),
        node(
          "p",
          "Cost is split by approved load only. Pending loads are not included.",
          "help",
        ),
      );
      estimate.participants.forEach((p) => {
        const name =
          view.members.find((m) => m.user_id === p.participant_id)?.name ||
          "You";
        qc.append(
          node(
            "div",
            name +
              ": " +
              money(p.share_inr) +
              " shared · " +
              money(p.individual_cost_inr) +
              " alone · saves " +
              money(p.savings_inr),
            "quote-row",
          ),
        );
      });
      if (!estimate.all_participants_benefit)
        qc.append(
          node(
            "p",
            "At least one farmer would pay more than travelling alone. This group cannot be locked with this split.",
            "notice",
          ),
        );
    } catch (e) {
      qc.append(node("p", e.message, "notice"));
    }
  } else
    qc.append(
      node(
        "p",
        "Your cost share appears after your load is approved. The organizer reviews the combined load and rates.",
      ),
    );
  chatAllowed = owner || own?.status === "APPROVED";
  $("chat-open").hidden = !chatAllowed;
  $("chat-locked").hidden = chatAllowed;
  $("chat-refresh").disabled = !chatAllowed;
  $("chat-form").hidden = ["CANCELLED", "SETTLED"].includes(active.state);
  if (chatAllowed) await chat();
}
async function transition(target) {
  let body = { target, expected_version: view.version };
  if (target === "LOCKED") {
    if (
      !confirm(
        "Lock this group? New requests and load changes will stop. Confirm rates, availability and agreement with the farmers first.",
      )
    )
      return;
  } else if (target === "DISPATCHED") {
    body.transport_reference = prompt(
      "Enter the agreed transporter / vehicle reference (not a payment detail):",
    );
    if (!body.transport_reference) return;
  } else {
    body.note = prompt(
      target === "CANCELLED"
        ? "Why is this trip cancelled?"
        : "Enter a completion note (this does not transfer money):",
    );
    if (!body.note) return;
  }
  await api("/v1/pools/" + active.id + "/transition", body);
  await openTrip(active.id);
}
async function chat() {
  if (!chatAllowed) return;
  const rows = await api("/portal/api/trips/" + active.id + "/messages");
  $("messages").replaceChildren();
  if (!rows.length)
    $("messages").append(
      node(
        "p",
        "No messages yet. Introduce yourself and agree on the pickup plan.",
        "help",
      ),
    );
  rows.forEach((m) => {
    const row = node("div", undefined, "message");
    row.append(
      node("strong", m.name),
      node("p", m.body),
      node(
        "small",
        new Date(
          m.created_at.endsWith("Z") ? m.created_at : m.created_at + "Z",
        ).toLocaleString(),
      ),
    );
    $("messages").append(row);
  });
}
$("chat-form").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    await api("/portal/api/trips/" + active.id + "/messages", {
      body: $("message").value,
    });
    $("message").value = "";
    await chat();
  });
};
$("chat-refresh").onclick = () => run(chat);
$("post-open").onclick = () => {
  if (needUser()) show("post");
};
$("post-back").onclick = $("detail-back").onclick = () =>
  run(async () => {
    show("browse");
    await list();
  });
$("detail-refresh").onclick = () => run(() => openTrip(active.id));
$("discover").onclick = () =>
  run(async () => {
    mode = "discover";
    await list();
  });
$("mine").onclick = () => {
  if (needUser())
    run(async () => {
      mode = "mine";
      await list();
    });
};
$("refresh").onclick = () => run(() => list());
$("more").onclick = () => run(() => list(true));
$("search-form").onsubmit = (e) => {
  e.preventDefault();
  run(() => list());
};
$("post-form").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    $("post-submit").disabled = true;
    try {
      const t = await api("/portal/api/trips", {
        origin: $("p-origin").value,
        destination: $("p-destination").value,
        state: $("p-state").value,
        district: $("p-district").value,
        travel_date: $("p-date").value,
        commodity: $("p-crop").value,
        pickup_description: $("p-pickup").value,
        distance_km: $("p-distance").value,
        max_quantity_quintals: $("p-max").value,
        lot: lot("own"),
        vehicles: editor.values(),
      });
      toast("Trip published. Other farmers can now request to join.");
      await openTrip(t.id);
    } finally {
      $("post-submit").disabled = false;
    }
  });
};
$("auth-close").onclick = () => $("auth").close();
$("auth-toggle").onclick = () => {
  registering = !registering;
  $("registration").hidden = !registering;
  $("a-name").required = $("a-village").required = registering;
  $("a-password").minLength = registering ? 15 : 1;
  $("a-password").autocomplete = registering
    ? "new-password"
    : "current-password";
  $("auth-title").textContent = $("auth-submit").textContent = registering
    ? "Create account"
    : "Sign in";
  $("auth-toggle").textContent = registering
    ? "Sign in instead"
    : "Create an account instead";
  $("auth-error").hidden = true;
};
$("auth-form").onsubmit = async (e) => {
  e.preventDefault();
  $("auth-error").hidden = true;
  $("auth-submit").disabled = true;
  try {
    let body = { username: $("a-user").value, password: $("a-password").value };
    if (registering)
      Object.assign(body, {
        name: $("a-name").value,
        village: $("a-village").value,
      });
    user = await api(
      "/portal/api/" + (registering ? "register" : "login"),
      body,
    );
    $("a-password").value = "";
    $("auth").close();
    identity();
    if (!$("detail").hidden) await openTrip(active.id);
    else await list();
    toast("Signed in. You can post a trip or request to join one.");
  } catch (e) {
    $("auth-error").textContent = e.message;
    $("auth-error").hidden = false;
  } finally {
    $("auth-submit").disabled = false;
  }
};
run(async () => {
  try {
    user = await api("/v1/me");
  } catch {}
  identity();
  await list();
});
