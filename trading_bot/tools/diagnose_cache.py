import sys
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from trading_bot.config import Config

print('FDR_CACHE_DIR =', Config.FDR_CACHE_DIR)
cache_dir = Path(Config.FDR_CACHE_DIR)
if not cache_dir.exists():
    print('cache dir does not exist')
else:
    files = sorted(list(cache_dir.iterdir()), key=lambda p: p.name)
    print('files count:', len(files))
    for p in files[:20]:
        try:
            st = p.stat()
            print(p.name, st.st_size, time.ctime(st.st_mtime))
        except Exception as e:
            print('err stat', p, e)
