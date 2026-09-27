# LuxStay — Homestay Booking Website

**Topic:** C3 – Homestay Booking
**Group:** 2 — AI66B
**Repository:** https://github.com/WEB-FDA-NEU/AI66B---G2---TOPIC-C3---WEB-DESIGN-AND-PROGRAMMING

---

## 3.1. Project Overview

LuxStay is a front-end prototype of an online homestay booking platform that connects
travellers with homestay hosts across Vietnam. Visitors can search and filter homestays,
view full listing details, pick dates and see room availability inline, and complete a
mock booking and payment flow. Registered customers can track their booking history and
cancel bookings. Approved hosts can manage their homestays, rooms, pricing/availability,
and incoming bookings through a dedicated dashboard. An administrator reviews and
approves/rejects host applications.

This submission (Milestone 2) implements the interface layer only: static HTML/CSS/JS
pages wired together with client-side navigation and mock JSON data (`frontend/mock/`).
No real backend/database calls are made from these pages in this milestone.

---

## 3.2. Implemented Screens and Features

All 16 core screens required for Milestone 2, plus 3 additional screens the team chose
to build (Host Registration, Host Booking Management, and a dedicated Room/Date
Selection step), are implemented.

| # | Screen | File | Key features | Status |
|---|--------|------|---------------|--------|
| 1 | Home | `index.html` | Search bar, featured homestays, popular destinations | Completed |
| 2 | Search Results | `search.html` | Filter sidebar (price, room type, amenities, rating, dates), sort, pagination, empty state | Completed |
| 3 | Homestay Detail (incl. Room Selection) | `detail.html` | Photo gallery, description, amenities, location text, price, rating, reviews, date picker with rooms shown inline, empty state for no availability | Completed |
| 4 | Room / Date Selection *(bonus)* | `booking-select.html` | Guest & room count picker, per-room price calculation, proceeds to checkout | Completed |
| 5 | Login | `login.html` | Email/password form, inline validation errors, link to Register | Completed |
| 6 | Register | `register.html` | Name, email, phone, password + confirm, terms checkbox, validation | Completed |
| 7 | Host Registration *(bonus)* | `host-register.html` | Apply to become a host, shares validation logic with Login/Register | Completed |
| 8 | Booking Page (incl. Payment) | `booking-page.html` | Step 1: dates/guests + cost breakdown (nights × price + 5% service fee); Step 2: mock payment form (card number, expiry, CVV) in the same page | Completed |
| 9 | Booking Confirmation | `booking-confirmed.html` | Booking reference, homestay info, dates, total cost, host contact | Completed |
| 10 | Booking History | `booking-list.html` | List of bookings grouped by status, empty state | Completed |
| 11 | Booking Detail | `booking-detail.html` | Full details, status timeline, Cancel button with confirmation modal and cancellation policy note | Completed |
| 12 | Profile | `profile.html` | Name, email, phone, avatar, change password | Completed |
| 13 | Admin Dashboard (incl. Host Applications) | `admin.html` | Pending host application queue, summary stats, approve/reject with reason | Completed |
| 14 | Host Dashboard | `host-dashboard.html` | Homestay/room/booking counts, recent reviews, quick links | Completed |
| 15 | Homestay Management | `host-homestays.html` | List of host's homestays with status counts, edit/soft-delete/view rooms, empty state | Completed |
| 16 | Homestay Form (Add/Edit) | `host-homestay-form.html` | Name, description, location, amenities (multi-select), photo upload (1–10), delete action on edit mode | Completed |
| 17 | Room Management (incl. Room Form) | `host-rooms.html` | Room list per homestay + inline add/edit form (type, capacity, description, price, photos, availability calendar) | Completed |
| 18 | Host Booking Management *(bonus)* | `host-bookings.html` | List of bookings across host's homestays, status updates | Completed |
| 19 | 404 — Not Found | `404.html` | Friendly message with links back to Home/Search | Completed |

**Shared components** (used across screens): site header/footer (`js/components/`),
homestay card, booking status badge, toast notifications, confirmation modal — all
implemented in `js/` and `css/components.css`.

> All required screens and features for this milestone are implemented. See section 3.5.

---

## 3.3. Instructions to Open/Run the Project

1. Unzip the submitted file.
2. Open `index.html` directly in a modern web browser (Chrome, Edge, or Firefox
   recommended) — either double-click the file or drag it into the browser window.
3. No build step, server, or installation is required. All pages are static HTML/CSS/JS
   and use mock JSON data under `mock/` for content (homestays, rooms, bookings, users).
4. Navigation between all implemented screens works via the links/buttons on each page
   (e.g., Home → Search → Homestay Detail → Room Selection → Booking → Payment →
   Confirmation; Login/Register; Host Dashboard → Homestay/Room Management → Host
   Bookings; Admin Dashboard).
5. Some actions that would normally require a real login session (e.g., booking a room)
   check a mock/local login state — log in via `login.html` or `register.html` first if
   a page redirects you there.

---

## 3.4. Team Members and Individual Contributions

| No. | Student ID | Full Name | Assigned Screens/Pages | Main Contributions | Status |
|-----|-----------|-----------|--------------------------|----------------------|--------|
| 1 | 11247257 | Duong Duc Anh | Home (`home.html`), Search Results (`search.html`), Homestay Detail (`detail.html`), 404 (`404.html`), Room/Date Selection (`booking-select.html`) | Implemented the home page, search results with filter sidebar and pagination, homestay detail page with photo gallery and inline room availability, the room/date selection step, and the 404 error page. Built the shared homestay card component. Also add motion to the frontend and help code the finalize frontend. | Completed |
| 2 | 11247308 | Hoang Thi Phuong Linh | Login (`login.html`), Register (`register.html`), Host Registration (`host-register.html`), Booking Page (`booking-page.html`), Booking Confirmation (`booking-confirmed.html`) | Implemented login and registration forms with client-side validation, the host application form (sharing auth/validation logic with customer register), and the combined booking + mock payment flow with cost breakdown and the booking confirmation screen. | Completed |
| 3 | 11247298 | Nguyen Quang Huy | Booking History (`booking-list.html`), Booking Detail (`booking-detail.html`), Profile (`profile.html`), Admin Dashboard (`admin.html`) | Implemented the customer booking history list with status grouping, booking detail page with cancellation modal and policy messaging, the profile management page, and the admin dashboard with the host application review/approve/reject queue. Update Duc Anh and Phuong Linh works to match the group. | Completed |
| 4 | 11247296 | Le Sy Huy | Host Dashboard (`host-dashboard.html`), Homestay Management (`host-homestays.html`), Homestay Form (`host-homestay-form.html`), Room Management (`host-rooms.html`), Host Booking Management (`host-bookings.html`) | Implemented the host dashboard overview, homestay list/management with soft delete, the shared add/edit homestay form, the room management page with inline add/edit form and availability calendar, and the host-side booking management list. Help code the finalize frontend. | Completed |


---

## 3.5. Incomplete Features and Screens

All required screens and features for Milestone 2 are completed. There are no
partially implemented or missing screens/features in this submission.


---

## 4. Actual ZIP Structure

```
team2.zip
│
├── index.html
├── README.md
├── home.html
├── search.html
├── detail.html
├── booking-select.html
├── login.html
├── register.html
├── host-register.html
├── booking-page.html
├── booking-confirmed.html
├── booking-list.html
├── booking-detail.html
├── profile.html
├── admin.html
├── host-dashboard.html
├── host-homestays.html
├── host-homestay-form.html
├── host-rooms.html
├── host-bookings.html
├── 404.html
│
├── css/
│   ├── reset.css
│   ├── tokens.css
│   ├── layout.css
│   ├── components.css
│   └── motion.css
│
├── js/
│   ├── api.js
│   ├── auth.js
│   ├── config.js
│   ├── render.js
│   ├── ui.js
│   ├── motion.js
│   ├── components/
│   │   ├── site-header.js
│   │   └── site-footer.js
│   └── pages/
│       ├── home.js
│       ├── list.js
│       ├── detail.js
│       ├── login.js
│       ├── register.js
│       ├── host-register.js
│       ├── booking-list.js
│       ├── host-dashboard.js
│       ├── host-homestays.js
│       ├── host-homestay-form.js
│       ├── host-rooms.js
│       └── host-bookings.js
│
├── mock/
│   ├── items.json
│   ├── item-1.json
│   ├── bookings.json
│   ├── users.json
│   ├── host-homestays.json
│   ├── host-rooms.json
│   └── host-bookings.json
│
└── img/
    ├── avatar_default.jpg
    ├── anh_dai_dien.jpg
    └── da lat.png
```

> Note: only the contents of the `frontend/` folder from the group repository are
> included in this ZIP — the `backend/` and `docs/` folders are excluded, since this
> milestone only requires the implemented front-end interface. `index.html` sits at the
> root of the ZIP as the entry page.