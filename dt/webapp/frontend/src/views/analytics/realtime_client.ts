type Handler = (payload: unknown) => void;

function ensureSocketIoAvailable() {
  const io = window.io;
  if (!io) {
    throw new Error("Socket.IO client is not available on window.io");
  }
  return io;
}

export function createRealtimeClient() {
  const handlersByEvent = new Map<string, Set<Handler>>();

  let socket: any = null;
  const boundEvents = new Set<string>();

  function bindEvent(eventName: string) {
    if (!socket || boundEvents.has(eventName)) {
      return;
    }
    boundEvents.add(eventName);
    socket.on(eventName, (payload: unknown) => {
      const handlers = handlersByEvent.get(eventName);
      if (!handlers) {
        return;
      }
      for (const handler of handlers) {
        handler(payload);
      }
    });
  }

  function start() {
    if (socket) {
      return;
    }
    const io = ensureSocketIoAvailable();
    socket = io();
    for (const eventName of handlersByEvent.keys()) {
      bindEvent(eventName);
    }
  }

  function subscribe(eventName: string, handler: Handler) {
    let handlers = handlersByEvent.get(eventName);
    if (!handlers) {
      handlers = new Set();
      handlersByEvent.set(eventName, handlers);
    }
    handlers.add(handler);
    bindEvent(eventName);

    return () => {
      const current = handlersByEvent.get(eventName);
      if (!current) {
        return;
      }
      current.delete(handler);
      if (current.size === 0) {
        handlersByEvent.delete(eventName);
      }
    };
  }

  return {
    start,
    subscribe,
  };
}

export const realtimeClient = createRealtimeClient();

