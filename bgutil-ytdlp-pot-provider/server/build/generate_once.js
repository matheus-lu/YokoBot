import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import { join, dirname } from 'path';
const __dirname = dirname(fileURLToPath(import.meta.url));
const tsx = join(__dirname, '..', 'node_modules', '.bin', 'tsx');
const ts = join(__dirname, '..', 'src', 'generate_once.ts');
execFileSync(tsx, [ts, ...process.argv.slice(2)], { stdio: 'inherit' });
