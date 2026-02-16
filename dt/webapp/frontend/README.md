# Webapp Frontend (Svelte)

This folder contains the Svelte frontend for the Digital Twin dashboard.

## Dev

```bash
cd dt/webapp/frontend
npm install
npm run dev
```

## Build for Flask

The Flask webapp serves the built UI under `/ui/`. Build output is written to `dt/webapp/static/ui`.

```bash
cd dt/webapp/frontend
npm install
npm run build
```

Then run the dashboard backend and open:
- `http://127.0.0.1:5000/ui/`

