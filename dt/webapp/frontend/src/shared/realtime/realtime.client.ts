/**
 * @fileoverview Wrapper around the Socket.IO client.
 * Manages the connection and routes incoming socket events to registered handlers.
 */

import { io } from "socket.io-client";
import { SubscriptionToken } from "./subscription.token";

// Type definition for event handlers that receive payloads from Socket.IO events.
export type RealtimeHandler = (payload: unknown) => void;

/**
 * Creates a lightweight wrapper around Socket.IO to manage pub/sub event subscriptions.
 * Allows components to subscribe to backend events before the connection is actually established.
 */
export class RealtimeClient {
	private handlersByEvent = new Map<string, Set<RealtimeHandler>>();
	private socket: any = null; // Will hold the Socket.IO client instance once initialized.
	private boundEvents = new Set<string>(); // Tracks which events have already been bound to avoid duplicate listeners.

	/** Binds a Socket.IO event to the client, routing incoming messages to registered handlers. */
	private bindEvent(eventName: string) {
		if (!this.socket || this.boundEvents.has(eventName)) {
			return;
		}
		this.boundEvents.add(eventName);
		// Listen for the event on the Socket.IO client and dispatch to all registered handlers.
		this.socket.on(eventName, (payload: unknown) => {
			const handlers = this.handlersByEvent.get(eventName);
			if (!handlers) return;
			for (const handler of handlers) {
				handler(payload);
			}
		});
	}

	/** Initializes the Socket.IO connection and binds any pre-registered event listeners. */
	start() {
		if (this.socket) return;
		this.socket = io();
		for (const eventName of this.handlersByEvent.keys()) {
			this.bindEvent(eventName);
		}
	}

	/**
	 * Subscribes a handler to a specific Socket.IO event.
	 * @param eventName - The event topic to listen for.
	 * @param handler - The callback function to execute on message receipt.
	 * @returns A cleanup function to remove the subscription.
	 */
	subscribe(eventName: string, handler: RealtimeHandler): SubscriptionToken {
		this.start();

		let handlers = this.handlersByEvent.get(eventName);
		if (!handlers) {
			handlers = new Set();
			this.handlersByEvent.set(eventName, handlers);
		}
		handlers.add(handler);
		this.bindEvent(eventName);

		// Return an unsubscribe function that removes the handler from the set of listeners for this event.
		return new SubscriptionToken(() => {
			const current = this.handlersByEvent.get(eventName);
			if (!current) return;
			current.delete(handler);
			// If there are no more handlers for this event, we can optionally unbind it from the Socket.IO client.
			if (current.size === 0) {
				this.handlersByEvent.delete(eventName);
				if (this.socket) {
					this.socket.off(eventName);
					this.boundEvents.delete(eventName);
				}
			}
		});
	}
}

/** Singleton instance of the realtime client. */
export const realtimeClient = new RealtimeClient();
