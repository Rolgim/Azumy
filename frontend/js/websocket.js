export const API = 'http://localhost:8000';
export const WS  = 'ws://localhost:8000';
 
export function openWS(path, payload, handlers) {
  const ws = new WebSocket(WS + path);
  ws.onopen    = () => ws.send(JSON.stringify(payload));
  ws.onmessage = e  => { const m = JSON.parse(e.data); handlers[m.type]?.(m); };
  ws.onerror   = ()  => handlers.error?.({ message: 'WebSocket error — is the server running?' });
  return ws;
}