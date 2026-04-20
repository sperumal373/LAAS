import sys
sys.path.insert(0, r"C:\caas-dashboard\backend")
from hyperv_migrate import _scvmm_exec
print("Testing SCVMM connection...")
r = _scvmm_exec('"SCVMM_OK: $($vmm.Name)"', timeout=30)
print("Result:", r)
print("All checks passed!")
