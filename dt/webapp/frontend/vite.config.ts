import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
	base: "/",
	plugins: [svelte()],
	resolve: {
		alias: {
			$features: "/src/features",
			$shared: "/src/shared",
		},
	},
	server: {
		proxy: {
			"/api": {
				target: "http://localhost:5000",
				changeOrigin: true,
			},
		},
	},
	build: {
		outDir: "./ui",
		emptyOutDir: true,
		sourcemap: true,
	},
});
