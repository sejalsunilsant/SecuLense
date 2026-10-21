import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const python = process.platform === 'win32'
  ? (existsSync(path.join(root, '.venv', 'Scripts', 'python.exe')) ? path.join(root, '.venv', 'Scripts', 'python.exe') : 'python')
  : (existsSync(path.join(root, '.venv', 'bin', 'python')) ? path.join(root, '.venv', 'bin', 'python') : 'python3');
const exported = spawnSync(python, ['scripts/export_react_dashboard.py'], { cwd: root, stdio: 'inherit' });
if (exported.status !== 0) process.exit(exported.status ?? 1);

const viteEntry = path.join(here, 'node_modules', 'vite', 'bin', 'vite.js');
if (!existsSync(viteEntry)) {
  console.error('Frontend packages are missing. Run npm install in the frontend folder first.');
  process.exit(1);
}

const api = spawn(python, ['-u', 'scripts/local_web_server.py'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
let apiReady = false;
const apiReadyPromise = new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error('Local auth API did not start on port 8765.')), 10000);
  api.stdout.on('data', (chunk) => {
    const output = chunk.toString(); process.stdout.write(output);
    if (output.includes('listening on')) { apiReady = true; clearTimeout(timeout); resolve(); }
  });
  api.stderr.on('data', (chunk) => process.stderr.write(chunk));
  api.on('error', (error) => { clearTimeout(timeout); reject(error); });
  api.on('exit', (code) => { if (!apiReady) { clearTimeout(timeout); reject(new Error(`Local auth API exited before starting (code ${code}).`)); } });
});
try { await apiReadyPromise; }
catch (error) { api.kill(); console.error(error.message); process.exit(1); }

const server = spawn(process.execPath, [viteEntry, '--host', '127.0.0.1'], { cwd: here, stdio: 'inherit' });
let stopping = false;
function stop(signal) {
  if (stopping) return;
  stopping = true;
  server.kill(signal);
  api.kill(signal);
}
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => stop(signal));
server.on('error', (error) => { console.error(`Could not start the React site: ${error.message}`); api.kill(); process.exit(1); });
api.on('exit', (code) => { if (!stopping) { server.kill(); process.exit(code ?? 1); } });
server.on('exit', (code) => { if (!stopping) { stopping = true; api.kill(); } process.exit(code ?? 0); });
