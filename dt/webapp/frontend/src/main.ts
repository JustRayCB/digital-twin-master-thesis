/**
 * @fileoverview Main entry point for the Digital Twin frontend application.
 * Bootstraps the Svelte application, mounts the root component, and imports global styles and configurations.
 */

import App from "./App.svelte";
import { mount } from "svelte";

// Global styles
import "./styles/global.css";
import "./styles/components.css";

/**
 * Mounts the root Svelte component to the DOM.
 * @remarks The `apiBase` prop is injected here, allowing configuration of the backend API path.
 */
mount(App, {
  target: document.getElementById("app")!,
  props: {
    apiBase: "/api",
  },
});
