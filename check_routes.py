import sys
sys.path.insert(0, r'C:\caas-dashboard\backend')
import os
os.chdir(r'C:\caas-dashboard\backend')

import logging
logging.disable(logging.CRITICAL)

try:
    import importlib
    m = importlib.import_module('main')
    rvtools = [r.path for r in m.app.routes if hasattr(r, 'path') and 'rvtools' in r.path]
    print('rvtools routes:', rvtools)
    print('total routes:', len(m.app.routes))
except Exception as e:
    import traceback
    traceback.print_exc()
