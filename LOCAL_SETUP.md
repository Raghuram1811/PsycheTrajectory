# PsycheTrajectory — local setup

This repository contains the editable source for the PsycheTrajectory wellness simulator.

## Requirements

- Node.js 22.13 or newer
- npm
- macOS, Linux, or Windows with WSL

## Run locally

Open a terminal in this folder and run:

```bash
npm install
npm run dev
```

Then open the local address printed in the terminal (normally `http://localhost:5173`).

Stop the server with `Ctrl+C`.

## Edit the site

The main files are:

- `app/page.tsx` — page content, simulator logic, and interactions
- `app/globals.css` — colors, typography, layout, and responsive styling
- `public/` — static images and other browser assets

Saving a change while `npm run dev` is running refreshes the browser automatically.

## Test a production build

```bash
npm run build
npm run start
```

## Open it to other devices on the same network

```bash
npm run dev -- --host 0.0.0.0
```

Use the network address printed in the terminal. Your firewall may ask for permission.

## Share it publicly

For a durable public link, keep the project in a private GitHub repository and connect that repository to a compatible hosting provider, or publish a new checkpoint through ChatGPT Sites. Do not use a temporary development server for clinical pilots or real participant data.

## Important product boundary

The current simulator is a demonstration. It uses in-browser sample state and does not persist participant records. Before collecting real mental-health information, add explicit consent, authentication, encryption, access controls, auditability, retention/deletion policies, and an appropriate clinical/privacy review.
