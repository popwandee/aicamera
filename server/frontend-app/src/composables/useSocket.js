import { io } from 'socket.io-client';
import { ref } from 'vue';

let socket = null;
const connected = ref(false);

function getSocket() {
  if (!socket) {
    socket = io(window.location.origin, {
      path: '/ws/',
      transports: ['websocket', 'polling'],
      reconnectionDelay: 2000,
      reconnectionAttempts: Infinity,
    });
    socket.on('connect',    () => { connected.value = true; });
    socket.on('disconnect', () => { connected.value = false; });
  }
  return socket;
}

export function useSocket() {
  const sio = getSocket();
  return { socket: sio, connected };
}

export default useSocket;
