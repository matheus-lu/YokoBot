import subprocess, sys, os, shutil
os.environ['HOME'] = '/application'

local_site = '/application/.local/lib/python3.13/site-packages'
if local_site not in sys.path:
    sys.path.insert(0, local_site)

print("Instalando dependências...")
subprocess.run([sys.executable, '-m', 'pip', 'install',
     'discord.py>=2.4.0', 'aiosqlite', 'aiohttp',
     'yt-dlp', 'yt-dlp-ejs', 'Pillow', 'PyNaCl', 'beautifulsoup4', 'requests', '-q'],
    capture_output=True)

# Desinstalar OAuth2 obsoleto
subprocess.run([sys.executable, '-m', 'pip', 'uninstall', 'yt-dlp-youtube-oauth2', '-y'],
    capture_output=True)
print("✅ Dependências instaladas!")

# Wrapper ESM para o bgutil
bgutil_server_dir = "/application/bgutil-ytdlp-pot-provider/server"
generate_once_js = f"{bgutil_server_dir}/build/generate_once.js"
os.makedirs(f"{bgutil_server_dir}/build", exist_ok=True)
with open(generate_once_js, 'w') as f:
    f.write('''import { execFileSync } from 'child_process';
import { fileURLToPath } from 'url';
import { join, dirname } from 'path';
const __dirname = dirname(fileURLToPath(import.meta.url));
const tsx = join(__dirname, '..', 'node_modules', '.bin', 'tsx');
const ts = join(__dirname, '..', 'src', 'generate_once.ts');
execFileSync(tsx, [ts, ...process.argv.slice(2)], { stdio: 'inherit' });
''')

# Plugin bgutil
yt_dlp_site_plugins = f"{local_site}/yt_dlp_plugins/extractor"
os.makedirs(yt_dlp_site_plugins, exist_ok=True)
extracted = "/application/.yt-dlp/plugins/yt_dlp_plugins/extractor"
if os.path.exists(extracted):
    for f in os.listdir(extracted):
        if f.startswith("getpot_bgutil"):
            src = os.path.join(extracted, f)
            dst = os.path.join(yt_dlp_site_plugins, f)
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)

import runpy
runpy.run_path("main.py", run_name="__main__")