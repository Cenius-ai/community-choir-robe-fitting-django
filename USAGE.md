# Using Community Choir Robe Fitting

Two people use this app: the **choir director**, who manages everything, and a **singer**,
who only ever sees their own robe. Everything is server-rendered — every form is a normal
POST with server-side validation, so the whole product works without JavaScript.

## Signing in

1. Open <http://127.0.0.1:8000/> — you are redirected to `/accounts/login/`.
2. Sign in with `cenius` / `cenius` (or `cenius@cenius.ai` / `cenius`), or tap
   **Sign in as the demo director**. Singers use their own username and password.
3. The director lands on `/dashboard/`; a singer lands on `/me/`.
4. A wrong password shows one message — *Those credentials did not match our records* — and
   keeps the username you typed. It never says which field was wrong.
5. **Sign out** is always in the top bar and returns you to the sign-in card with a notice.

If a singer opens a director page (`/singers/`, `/dashboard/`, …) the server answers 403
with a link straight back to their own robe page — nothing is written to the database.

## The director dashboard (`/dashboard/`)

The bento shows, live from the database:

- **Open alterations** (the anchor cell) — up to five open tickets with singer, size and due
  date; each links to the ticket. When nothing is open it reads *"Nothing needs attention —
  the queue is clear"* with links to the roster and venues.
- **Singers in the roster**, **No robe size yet**, **Open alterations** (with the queued
  count) and **Concert venues** counts.
- **Singers still awaiting a robe size** — links to each singer's page.
- **Quick links** to roster, alterations, robe sizes and venues.

## Managing the roster (`/singers/`)

- Search by name, and narrow by voice part with the chips (Soprano / Alto / Tenor / Bass).
  Both combine; a search with no hits shows *"No singers match that search — clear filters
  or add a singer"*.
- Add a singer with the form in the right-hand card: name and voice part are required, and a
  blank name re-renders the form with an inline error instead of saving.
- A new singer appears at the top of the roster with an **Unassigned** size chip.

## Assigning a robe size and raising an alteration (`/singers/<id>/`)

- Pick a size from the catalog, add optional notes, and **Save fitting**. The detail page
  and the roster chip immediately show the size code with its chest range.
- Ticking **Needs alteration** with a seamstress note creates a queued ticket on save.
  The flag is rejected unless a robe size is assigned, and a singer who already has an open
  ticket gets a notice instead of a duplicate.
- Choosing **Unassigned** clears the size and raises the dashboard's "no robe size yet" count.
- **Alteration history** lists every ticket for the singer with its status badge, linking to
  the ticket. **Delete singer** asks for confirmation once more before removing anything.

## The robe size catalog (`/robes/`)

- Each row shows the size code, chest range, length in inches and how many singers wear it.
- Open a row to edit its code, chest range, length or note in place.
- Chest ranges are validated (`38-40`) and the length must be a whole number of inches;
  invalid input re-renders with the message at the field.
- **Delete size** is refused while singers still wear it — the page names the count.
- With an empty catalog you get *"Add your first robe size — sizes you create here become
  assignable to singers"*.

## The alteration queue (`/alterations/`)

- Tabs **All / Queued / In progress / Done** with a count on each; the tab you pick filters
  the rows.
- Rows show singer, current size, requested date, a notes excerpt and the status badge.
- **New ticket** picks a singer, writes seamstress notes (required) and an optional due date;
  the ticket appears at the top of the queue as **Queued**.
- Open a ticket to edit multi-line seamstress notes (they persist exactly as typed), set the
  due date, and move the ticket **Queued → In progress → Done**. Setting Done stamps the
  completion date and drops the ticket out of the Queued tab while it stays visible under
  All and Done. Clicking the current status again is a no-op with a notice.
- **Delete ticket** confirms before removing anything.

## Venues and dress codes (`/venues/`)

- Each row shows the venue name, address and a one-line dress-code excerpt; open it for the
  full text.
- The detail page leads with the complete dress code in a quoted block, followed by the edit
  form. A blank dress code is rejected inline and the typed text is kept.
- **Delete venue** asks for confirmation, then removes the venue and its dress code.

## A singer's own page (`/me/`)

- Shows the singer's name, voice part, assigned size label with chest range and length, and
  a badge for their current alteration (Queued / In progress / Done).
- Nothing on the page can be edited, and **seamstress notes are never shown** to the singer.
- No size yet? *"No robe size assigned yet — your director will assign one; check back after
  your fitting."*
- An account not linked to a roster entry gets a polite "your account isn't linked yet"
  message instead of an error.

## Reference

- Login: `/accounts/login/` · Health probe: `/health/`
- Demo director: `cenius` / `cenius` · Demo singer: `nadia` / `singer-demo`
- Data lives in `db.sqlite3` next to `manage.py`; `python3 manage.py seed` restores the demo
  content at any time.
