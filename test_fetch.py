import sys, os, time
sys.path.insert(0, r'C:\caas-dashboard\backend')
os.chdir(r'C:\caas-dashboard\backend')
from dotenv import load_dotenv
load_dotenv()

t0 = time.time()
from vmware_client import get_all_data
try:
    data = get_all_data()
    t1 = time.time()
    print(f"get_all_data() took {t1-t0:.1f}s")
    print(f"Keys: {list(data.keys())}")
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
        elif isinstance(v, dict):
            print(f"  {k}: {len(v)} keys")
        else:
            print(f"  {k}: {type(v).__name__}")
except Exception as e:
    t1 = time.time()
    print(f"FAILED after {t1-t0:.1f}s: {e}")
