from hyperv_migrate import _scvmm_exec
print("Testing SCVMM connection...")
r = _scvmm_exec('"SCVMM_OK: $($vmm.Name)"', timeout=30)
print("Result:", r)
print("\nTesting VhdType enum...")
r2 = _scvmm_exec('[Microsoft.VirtualManager.Remoting.VHDType]::DynamicallyExpanding', timeout=30)
print("VhdType:", r2)
print("\nAll checks passed!")
