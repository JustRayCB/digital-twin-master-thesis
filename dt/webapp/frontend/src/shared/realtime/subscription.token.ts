/**
 * A token representing an active subscription. It can be used to clean up the subscription when it's no longer needed.
 */
export class SubscriptionToken {
	private active = true;

	public constructor(private readonly cleanupHandler: () => void) {}

	/** Cleans up the subscription if it's still active. */
	public cleanup() {
		if (!this.active) {
			return;
		}
		this.active = false;
		this.cleanupHandler();
	}
}

/** Composes multiple subscription tokens into a single token that cleans up all of them when invoked. */
export function composeSubscriptionTokens(tokens: SubscriptionToken[]) {
	return new SubscriptionToken(() => {
		for (const token of tokens) {
			token.cleanup();
		}
	});
}
