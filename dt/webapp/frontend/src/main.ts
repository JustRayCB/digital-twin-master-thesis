import App from "./App.svelte";

import { mount } from "svelte";
import "./styles/global.css";
import "./styles/components.css";
import "./views/analytics/plotly_globals";

mount(App, {
  target: document.getElementById("app")!,
  props: {
    apiBase: "/api",
  },
});
