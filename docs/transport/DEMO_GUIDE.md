# Transport calculator and farmer portal: demo guide

## Open the simple page

1. Extract the ZIP. Open its `backend` folder.
2. Double-click **START_DEMO.cmd**. If Windows hides file extensions, it may display as START_DEMO.
3. Wait for the browser to open **http://127.0.0.1:8001/demo**.
4. Keep the terminal window open. Press Ctrl+C when finished.

The first start needs Python 3.12 and an internet connection for packages. Later runs
reuse the local environment. If you already installed the backend packages, you can
also run `.\.venv\Scripts\python.exe -m mandiwise_transport.presentation` from VS Code's
terminal in the backend folder. The launcher creates a local SQLite database automatically
for the separate pooling portal; the calculator itself needs no account. A temporary
sign-in secret is generated automatically, so restarting requires signing in again.

If using the full backend's usual server on port 8000, restart it after installing this
updated source and open **http://127.0.0.1:8000/demo**. `/docs` remains the developer API
reference. The standalone launcher uses 8001 so it can coexist with that server.

## What to do on the page

- Start with the prefilled example and press **Calculate transport cost**.
- The result shows the cheapest combination, separate costs, shared costs and each person's bill.
- Read **How we calculated it** below the result. It expands the arithmetic for your inputs.
- Choose **3 farmers · 120 q**, then calculate again to demonstrate the capacity boundary.
- Change the distance or prices to show that the answers are calculated, not fixed.
- Use **Print result** for a handout or browser Save as PDF.

The route names are labels. Enter the actual road distance yourself; place names do
not trigger geocoding. All participants share that pickup point and destination.

## A one-minute explanation for your professor

"MandiWise aims to help farmers decide where to sell based on what they keep after
costs. This prototype demonstrates the transportation component.

We enter each farmer's quantity, the distance and the transport provider's prices.
In this illustrative example, a tempo carries 30 quintals and costs Rs 1000 plus
Rs 10 per km. At 60 km that is Rs 1600. A truck carries 100 quintals and costs
Rs 2500 plus Rs 20 per km, or Rs 3700.

One farmer with 40 quintals needs two tempos, costing Rs 3200. Two such farmers
travelling separately pay Rs 6400. Together, their 80 quintals fit into one truck
for Rs 3700. Each pays Rs 1850, saving Rs 1350.

The Python engine finds the cheapest whole-vehicle combination with sufficient
capacity. It splits the cost by quantity while keeping each farmer's produce separate."

## Be clear about what is demonstrated

These rates are invented classroom examples, clearly labelled on screen. The existing
AGMARKNET/CEDA datasets provide crop prices and historical arrivals, not road distances
or transport quotes. Real estimates require real inputs.

The presentation page exercises the same tested Python optimiser and split calculation
as the full backend. The calculator does not save pools. The separate **Farmer pooling**
page now provides accounts, saved trips, join approval, cost estimates and group chat.
Neither page arranges trucks, calculates crop-sale profit or moves money.

## Present the farmer pooling portal

1. Open **Farmer pooling** in the navigation and create an account.
2. Click **Post a pooling trip**. Enter a shared collection point, mandi, state/district,
   future date, checked distance, crop, group load limit and your own lot details.
3. Check or replace the example vehicle prices. Add/remove vehicle types as needed.
4. Publish. Your own lot is approved automatically; other farmers request approval.
5. Open the same portal URL in a private/incognito browser window, create a second
   account and find the first farmer's trip. Enter another lot and request to join.
6. In the organizer's window, press **Refresh trip**, review variety, grade and packing,
   and approve the request. In the second window, refresh to see the approval and share.
7. Use **Group chat** to agree on pickup time. Refresh chat to receive new messages.
8. After agreement, the organizer can **Lock group & cost split**. Pending requests must
   all be reviewed; the backend refuses a split that costs a farmer more than going alone.

For a clear example: two 40-quintal lots, 60 km, the initial tempo/truck rates, and a
100-quintal group limit yield a Rs 3700 group estimate and Rs 1850 per farmer.
These are classroom figures, not actual supplier quotes. Use suitable demo labels.

### What is saved and who sees it?

Accounts, trips, lots, approvals and messages persist in `backend/portal.db`. Do not
delete that file. Public discovery shows the organizer's name, meeting point, crop,
date, aggregate approved load and entered rates. The organizer sees each lot and share;
other farmers see only their own. Chat is restricted to the organizer and approved
members. An unapproved or withdrawn participant cannot read it.

This is a local prototype, not a publicly available farmer network. Farmers on separate
devices need a properly hosted shared server. Before public deployment, add HTTPS,
account verification/recovery, reporting/moderation, backups, shared rate limits and
operational monitoring. Names and supplier rates are not independently verified.
