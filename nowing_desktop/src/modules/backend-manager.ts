import path from 'path';
import { app } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import { getPort } from 'get-port-please';
import { showErrorDialog } from './errors';

const isDev = !app.isPackaged;
let backendPort = 4999;
let backendProcess: ChildProcess | null = null;

export function getBackendPort(): number {
  return backendPort;
}

function getBackendBinaryPath(): string {
  if (isDev) {
    // In development, assume running using uv run python
    return path.join(__dirname, '..', '..', 'nowing_backend', '.venv', 'bin', 'python');
  }
  // In production, assume binary is packaged in resources
  const platform = process.platform;
  const binaryName = platform === 'win32' ? 'nowing-backend.exe' : 'nowing-backend';
  return path.join(process.resourcesPath, 'backend', binaryName);
}

function getBackendArgs(port: number): string[] {
  if (isDev) {
    return ['-m', 'uvicorn', 'app.app:app', '--port', port.toString(), '--host', '127.0.0.1'];
  }
  // For the binary, it should accept port argument
  return ['--port', port.toString(), '--host', '127.0.0.1'];
}

function getBackendCwd(): string {
  if (isDev) {
    return path.join(__dirname, '..', '..', 'nowing_backend');
  }
  return path.join(process.resourcesPath, 'backend');
}

async function waitForBackend(url: string, maxRetries = 60): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 404 || res.status === 403 || res.status === 401) return true;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

export async function startFastAPIBackend(): Promise<void> {
  backendPort = await getPort({ port: 4999, portRange: [50_000, 60_000] });
  console.log(`Selected backend port ${backendPort}`);

  const binaryPath = getBackendBinaryPath();
  const args = getBackendArgs(backendPort);
  const cwd = getBackendCwd();

  console.log(`Starting backend: ${binaryPath} ${args.join(' ')}`);
  
  backendProcess = spawn(binaryPath, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PORT: String(backendPort)
    }
  });

  backendProcess.stdout?.on('data', (data) => {
    console.log(`[Backend]: ${data}`);
  });

  backendProcess.stderr?.on('data', (data) => {
    console.error(`[Backend ERR]: ${data}`);
  });

  backendProcess.on('exit', (code, signal) => {
    console.log(`Backend process exited with code ${code} and signal ${signal}`);
    backendProcess = null;
    if (code !== 0 && code !== null) {
      showErrorDialog('Backend Error', `FastAPI backend exited with code ${code}`);
    }
  });

  // Wait for the backend to be healthy
  const ready = await waitForBackend(`http://127.0.0.1:${backendPort}/api/v1/health`);
  if (!ready) {
    throw new Error('FastAPI backend failed to start within 30 seconds');
  }
  console.log(`FastAPI backend ready on port ${backendPort}`);
}

export function shutdownFastAPIBackend(): void {
  if (backendProcess) {
    console.log('Shutting down FastAPI backend...');
    try {
      // Send SIGTERM
      backendProcess.kill('SIGTERM');
      
      // Fallback kill if it doesn't die
      setTimeout(() => {
        if (backendProcess) {
          backendProcess.kill('SIGKILL');
        }
      }, 5000);
    } catch (e) {
      console.error('Error killing backend process', e);
    }
  }
}
