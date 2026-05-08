"""
hyperv_migrate.py - VMware -> Hyper-V via SCVMM (VM object method ONLY)

ROOT CAUSE FIX:
  vCenter 172.17.168.212 is registered in SCVMM as vcsa80u3-rookie.sdxtest.local
  (hostname, not IP). Old code searched by IP -> not found -> refresh never ran.
  FIX: Refresh ALL VirtualizationManagers, not just the one matching by IP.
"""
import os, time, json, traceback, subprocess

SCVMM_HOST   = "172.17.66.35"
SCVMM_SERVER = "SDXDCWRC02P3233"
SCVMM_USER   = r"sdxtest\zertohypv"
SCVMM_PASS   = "Wipro@123"
HV_HOST_FQDN = "sdxdcwrc02p3233.sdxtest.local"
HV_VM_PATH   = r"F:\Hyper-V-VM's"

VCENTER_CREDS = {
    "172.17.101.15":  {"user": "administrator@vsphere.local", "password": "Sdxdc@101-15"},
    "172.17.101.17":  {"user": "administrator@vsphere.local", "password": "Sdxdc@101-17"},
    "172.17.168.212": {"user": "administrator@vsphere.local", "password": "Sdxdc@168-212"},
    "172.17.80.150":  {"user": "administrator@vsphere.local", "password": "Sdxdc@80-150"},
    "172.17.73.191":  {"user": "administrator@vsphere.local", "password": "Sdxdc@73-191"},
    "172.16.6.125":   {"user": "administrator@vsphere.local", "password": "Sdxdr@6-125"},
}
