// Shared accessible vehicle editor. User input is never inserted as HTML.
class VehicleEditor {
  constructor(container, addButton, changed = () => {}) {
    this.container = container;
    this.button = addButton;
    this.changed = changed;
    this.serial = 0;
    addButton.onclick = () => {
      this.add();
      this.changed();
    };
    container.addEventListener("input", () => this.changed());
    this.add("Tempo", 30, 1000, 10);
    this.add("Truck", 100, 2500, 20);
  }
  add(name = "", capacity = 30, base = 0, km = 0) {
    if (this.container.children.length >= 12) return;
    const row = document.createElement("div");
    row.className = "vehicle";
    row.dataset.code = "vehicle-" + ++this.serial;
    const make = (caption, key, value, type, min, max, step) => {
      const wrap = document.createElement("div"),
        label = document.createElement("label"),
        input = document.createElement("input");
      input.id = this.container.id + "-" + this.serial + "-" + key;
      input.className = key;
      input.type = type;
      input.required = true;
      input.value = value;
      if (type === "number") {
        input.min = min;
        input.max = max;
        input.step = step;
      } else input.maxLength = 60;
      label.htmlFor = input.id;
      label.textContent = caption;
      wrap.append(label, input);
      return wrap;
    };
    row.append(make("Vehicle type / name", "vehicle-name", name, "text"));
    const fields = document.createElement("div");
    fields.className = "fields3";
    fields.append(
      make(
        "Capacity (quintals)",
        "vehicle-cap",
        capacity,
        "number",
        0.01,
        1000,
        0.01,
      ),
      make(
        "Fixed charge (₹)",
        "vehicle-base",
        base,
        "number",
        0,
        1000000,
        0.01,
      ),
      make("Rate / km (₹)", "vehicle-km", km, "number", 0, 1000000, 0.01),
    );
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "smallbtn";
    remove.textContent = "Remove vehicle type";
    remove.onclick = () => {
      if (this.container.children.length > 1) {
        row.remove();
        this.sync();
        this.changed();
      }
    };
    row.append(fields, remove);
    this.container.append(row);
    this.sync();
  }
  sync() {
    this.button.disabled = this.container.children.length >= 12;
    this.container
      .querySelectorAll("button")
      .forEach((b) => (b.disabled = this.container.children.length <= 1));
  }
  values() {
    return [...this.container.children].map((row) => ({
      code: row.dataset.code,
      name: row.querySelector(".vehicle-name").value.trim(),
      capacity_quintals: row.querySelector(".vehicle-cap").value,
      base_cost_inr: row.querySelector(".vehicle-base").value,
      per_km_inr: row.querySelector(".vehicle-km").value,
    }));
  }
  names() {
    return Object.fromEntries(
      [...this.container.children].map((row) => [
        row.dataset.code,
        row.querySelector(".vehicle-name").value.trim(),
      ]),
    );
  }
}
