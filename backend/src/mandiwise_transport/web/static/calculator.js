const $ = (id) => document.getElementById(id);
const money = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
const qty = (kg) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(kg / 100);
const label = (code) => vehicleEditor.names()[code] || code;
let serial = 0,
  revision = 0,
  calculated = false;
const vehicleEditor = new VehicleEditor(
  $("vehicles"),
  $("add-vehicle"),
  changed,
);
function changed() {
  revision++;
  if (calculated) {
    $("status").hidden = false;
    $("print").disabled = true;
    $("result").hidden = true;
    $("empty").hidden = false;
  }
}
function addFarmer(quantity = "40") {
  if ($("farmers").children.length >= 8) return;
  const id = ++serial,
    row = document.createElement("div");
  row.className = "farmer";
  row.innerHTML = `<div><label for="name-${id}">Farmer name</label><input id="name-${id}" class="farmer-name" maxlength="160" required></div><div><label for="quantity-${id}">Load (quintals)</label><input id="quantity-${id}" class="farmer-quantity" type="number" min="0.01" max="1000" step="0.01" required></div><button type="button" class="remove" aria-label="Remove farmer">×</button>`;
  row.querySelector(".farmer-name").value =
    `Farmer ${$("farmers").children.length + 1}`;
  row.querySelector(".farmer-quantity").value = quantity;
  row.querySelector("button").onclick = () => {
    if ($("farmers").children.length > 1) {
      row.remove();
      changed();
      syncButtons();
    }
  };
  $("farmers").append(row);
  syncButtons();
}
function syncButtons() {
  const count = $("farmers").children.length;
  $("add").disabled = count >= 8;
  document
    .querySelectorAll(".remove")
    .forEach((b) => (b.disabled = count <= 1));
}
function fleetText(vehicles) {
  return vehicles
    .map((v) => `${v.count} ${label(v.code)}${v.count > 1 ? "s" : ""}`)
    .join(" + ");
}
function paragraph(parent, text, cls) {
  const p = document.createElement("p");
  p.textContent = text;
  if (cls) p.className = cls;
  parent.append(p);
  return p;
}
function step(title, text) {
  const div = document.createElement("div");
  div.className = "calculation";
  const h = document.createElement("h3");
  h.textContent = title;
  div.append(h);
  paragraph(div, text, "formula");
  $("working").append(div);
}
function render(r, origin, destination) {
  $("result-title").textContent =
    `${r.participants.length} farmer${r.participants.length > 1 ? "s" : ""} · ${qty(r.quantity_kg)} quintals`;
  $("trip-summary").textContent =
    `${origin} → ${destination} · ${r.distance_km} km · Entered example inputs`;
  $("solo-total").textContent = money(r.individual_total_inr);
  $("pooled-total").textContent = money(r.cost_inr);
  $("saving-total").textContent = money(r.total_savings_inr);
  $("fleet").textContent = fleetText(r.vehicles);
  $("capacity").textContent =
    `${qty(r.quantity_kg)} q load / ${qty(r.capacity_kg)} q capacity. ${qty(r.unused_capacity_kg)} q spare capacity.`;
  $("warning").hidden = r.all_participants_benefit;
  $("warning").textContent =
    "This split makes at least one farmer pay more than travelling alone. Review the quantities and rates; the saved-pool backend would not allow this arrangement to be locked.";
  $("shares").replaceChildren();
  $("working").replaceChildren();
  $("explanation").replaceChildren();
  r.participants.forEach((p) => {
    const tr = document.createElement("tr"),
      name = document.createElement("td"),
      strong = document.createElement("strong"),
      small = document.createElement("small");
    strong.textContent = p.name;
    small.textContent = `${qty(p.quantity_kg)} q`;
    name.append(strong, small);
    tr.append(name);
    ["individual_cost_inr", "share_inr", "savings_inr"].forEach((key) => {
      const td = document.createElement("td");
      td.textContent = money(p[key]);
      if (key === "savings_inr")
        td.className = p.benefits_from_pooling ? "positive" : "negative";
      tr.append(td);
    });
    $("shares").append(tr);
  });
  r.rate_breakdown.forEach((v) =>
    step(
      `One ${label(v.code)} costs ${money(v.trip_cost_inr)}`,
      `${money(v.base_cost_inr)} fixed + (${money(v.per_km_inr)} × ${r.distance_km} km) = ${money(v.trip_cost_inr)}. Capacity: ${v.capacity_quintals} quintals.`,
    ),
  );
  r.participants.forEach((p) =>
    step(
      `${p.name} travelling alone`,
      `${qty(p.quantity_kg)} quintals needs ${fleetText(p.solo_vehicles)}, costing ${money(p.individual_cost_inr)}.`,
    ),
  );
  step(
    "Share enough vehicle capacity",
    `${qty(r.quantity_kg)} quintals fits in ${fleetText(r.vehicles)}. Total: ${money(r.cost_inr)}. The engine checks whole-vehicle combinations and picks the least expensive sufficient capacity.`,
  );
  r.participants.forEach((p) =>
    step(
      `${p.name}’s share`,
      `${qty(p.quantity_kg)} ÷ ${qty(r.quantity_kg)} × ${money(r.cost_inr)} ≈ ${money(p.share_inr)} after rounding. Savings: ${money(p.individual_cost_inr)} − ${money(p.share_inr)} = ${money(p.savings_inr)}.`,
    ),
  );
  paragraph(
    $("working"),
    "Shares are rounded to paise with any leftover paisa assigned deterministically, so the shares sum exactly to the total.",
    "help",
  );
  [
    `The inputs are each farmer’s quantity, a shared route distance, and the transport provider’s vehicle capacities and prices.`,
    `For this example, sending the farmers separately costs ${money(r.individual_total_inr)}. Combining their ${qty(r.quantity_kg)} quintals needs ${fleetText(r.vehicles)} and costs ${money(r.cost_inr)}.`,
    `The total saving is ${money(r.total_savings_inr)}. We split the transport bill in proportion to each farmer’s quantity, while keeping their produce separate.`,
    "This is the transport part of MandiWise. The wider project will combine transport with crop prices and other charges to estimate what the farmer keeps after selling.",
  ].forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    $("explanation").append(li);
  });
  $("empty").hidden = true;
  $("result").hidden = false;
  $("status").hidden = true;
  $("print").disabled = false;
  calculated = true;
}
document.querySelectorAll("[data-preset]").forEach(
  (button) =>
    (button.onclick = () => {
      $("farmers").replaceChildren();
      button.dataset.preset.split(",").forEach((q) => addFarmer(q));
      changed();
    }),
);
$("add").onclick = () => {
  addFarmer();
  changed();
};
$("calculator").addEventListener("input", changed);
$("print").onclick = () => window.print();
$("calculator").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("error").hidden = true;
  if (!$("calculator").reportValidity()) return;
  const body = {
    distance_km: $("distance").value,
    farmers: [...document.querySelectorAll(".farmer")].map((row) => ({
      name: row.querySelector(".farmer-name").value.trim(),
      quantity_quintals: row.querySelector(".farmer-quantity").value,
    })),
    vehicles: vehicleEditor.values(),
  };
  const started = revision,
    origin = $("origin").value.trim(),
    destination = $("destination").value.trim();
  $("calculate").disabled = true;
  $("calculate").textContent = "Calculating…";
  try {
    const response = await fetch("/demo/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      let message =
        result.error?.message ||
        result.detail ||
        "Please check the values and try again.";
      if (Array.isArray(message))
        message = message.map((e) => e.msg).join(" · ");
      throw new Error(message);
    }
    if (started === revision) {
      render(result, origin, destination);
      $("result").scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      $("status").hidden = false;
    }
  } catch (error) {
    $("result").hidden = true;
    $("empty").hidden = false;
    $("error").textContent =
      error instanceof TypeError
        ? "Could not reach the backend. Keep the launcher terminal open and try again."
        : error.message;
    $("error").hidden = false;
  } finally {
    $("calculate").disabled = false;
    $("calculate").textContent = "Calculate transport cost →";
  }
});
addFarmer("40");
addFarmer("40");
