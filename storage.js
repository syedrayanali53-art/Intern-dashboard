// The original board's host storage still works; ordinary browsers use localStorage.
if (!window.storage) {
  window.storage = {
    async get(key) { const value = localStorage.getItem(key); return value === null ? null : {value}; },
    async set(key, value) { localStorage.setItem(key, value); return {key}; }
  };
}
