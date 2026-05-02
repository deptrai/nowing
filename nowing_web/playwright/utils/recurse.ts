/**
 * Polling utility that executes a command until a condition is met.
 */
export async function recurse<T>(
  command: () => Promise<T>,
  check: (result: T) => boolean | Promise<boolean>,
  options: { timeout?: number; interval?: number; errorMsg?: string } = {}
): Promise<T> {
  const { timeout = 30000, interval = 1000, errorMsg = 'Recurse timeout exceeded' } = options;
  const start = Date.now();

  while (Date.now() - start < timeout) {
    const result = await command();
    if (await check(result)) {
      return result;
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }

  throw new Error(errorMsg);
}
