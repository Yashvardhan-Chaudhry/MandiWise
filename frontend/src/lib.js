export async function api(path, body) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-MandiWise-Request": "portal",
    },
    ...(body === undefined
      ? {}
      : { method: "POST", body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.error?.message || data?.detail;
    const error = new Error(
      Array.isArray(detail)
        ? detail.map((x) => `${x.loc.slice(1).join(".")}: ${x.msg}`).join("; ")
        : detail ||
            "Backend unavailable. Start the backend on port 8001 and retry.",
    );
    error.status = response.status;
    throw error;
  }
  return data;
}
export const money = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
export const quintals = (kg) => Number((Number(kg) / 100).toFixed(2));
export const indiaToday = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export function marketRows(rows) {
  return rows.filter(
    (r) =>
      r.state === "Punjab" &&
      Number.isFinite(Number(r.modal_price)) &&
      Number(r.modal_price) >= 50 &&
      Number(r.min_price) <= Number(r.modal_price) &&
      Number(r.modal_price) <= Number(r.max_price),
  );
}
export function localeText(catalogues, locale, key) {
  return catalogues[locale]?.[key] || catalogues.en[key] || key;
}

// Market names alone are not identities. Keep districts distinct, combine varieties.
export function candidateMarkets(rows) {
  return [
    ...new Map(
      rows
        .filter((r) => r.state === "Punjab")
        .map((r) => [
          JSON.stringify([r.market, r.district]),
          { market: r.market, district: r.district },
        ]),
    ).entries(),
  ].map(([id, market]) => ({ id, ...market }));
}
