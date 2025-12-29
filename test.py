import os
import re
import glob
import subprocess
import time

SUCCESS = 0
FAIL = 1


def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()


# ─────────────────────────────────────────────
# platform remoteproc driver probed
# ─────────────────────────────────────────────
def check_remoteproc():
    remoteproc = []
    for root, dirs, files in os.walk("/proc/device-tree/"):
        for d in dirs:
            if "remoteproc" in d:
                remoteproc.append(os.path.join(root, d))

    if not remoteproc:
        print("WARNING: remoteproc is not defind in device tree")
        return
    print("OK: remoteproc are defined:")
    print(remoteproc, sep="\n")

    path = "/sys/class/remoteproc/"
    if not any(os.scandir(path)):
        print(
            f"FAIL: remoteproc instance is not created, please make sure your remoteporc platform is load and be probeded"
        )
        return FAIL

    print("OK: remoteproc instance created (platform driver probed)")
    return SUCCESS


# ─────────────────────────────────────────────
# mailbox channels created
# (no notifyid here — mailbox does NOT know notifyid)
# ─────────────────────────────────────────────
def check_mailbox():
    mailboxs = []
    for root, dirs, files in os.walk("/proc/device-tree/"):
        for d in dirs:
            if d.startswith("mailbox"):
                mailboxs.append(os.path.join(root, d))
    if not mailboxs:
        print("WARNING: no mailbox is defined in device-tree")

    for node in mailboxs:
        dts = run(f"dtc -qqq -f -I fs -O dts {node}")
        interrupt = re.search(r"\binterrupts\s*=\s*<([^>]+)>;", dts)
        if not interrupt:
            raise RuntimeError("WARNING: no interrupts is defined for mailbox")


# ─────────────────────────────────────────────
# virtio RPMsg device created
# (THIS is where remoteproc_virtio has run)
# ─────────────────────────────────────────────
def check_virtio_device():
    vdevbuffer = []
    vdevring = []
    rsc_table = []
    for root, dirs, files in os.walk("/proc/device-tree/"):
        for d in dirs:
            if "vdev" in d and "buffer" in d:
                vdevbuffer.append(d)
            elif "vdev" in d and "vring" in d:
                vdevring.append(d)
            elif "rsc-table" in d:
                rsc_table.append(d)

    if not vdevbuffer:
        print("WARNING: vdevbuffer is not defined")
    print("OK: vdevbuffer define:")
    print(*vdevbuffer, sep="\n")

    if not vdevring:
        print("WARNING: vdev vrings are not defined")
    print("OK: vdev vring is are defined:")
    print(*vdevring, sep="\n")

    if not rsc_table:
        print("WARNING: resource table is not defined")
    print("OK: resource table is defined:")
    print(*rsc_table, sep="\n")

    virtio = glob.glob("/sys/bus/virtio/devices/virtio*")
    if not virtio:
        print("WARNING: no virtio devices created by remoteproc")
        return
    print(f"OK: virtio devices present: {virtio}")
    return virtio


# ─────────────────────────────────────────────
# RPMsg transport probe (virtio_rpmsg_bus)
# ─────────────────────────────────────────────
def check_rpmsg_transport(virtio_devices):
    for dev in virtio_devices:
        driver = os.path.join(dev, "driver")
        if os.path.islink(driver):
            drv = os.path.realpath(driver)
            if "virtio_rpmsg_bus" in drv:
                print(f"OK: rpmsg transport bound to {dev}")
                return
    raise RuntimeError("FAIL: virtio_rpmsg_bus not bound")


# ─────────────────────────────────────────────
# notifyid (kick id) validation
# (ONLY VALID HERE — after virtqueues exist)
# ─────────────────────────────────────────────
def check_notifyid_runtime():
    print("INFO: checking notifyid via runtime trace")

    # very rough example: look for notifyid in logs
    out = run("dmesg | grep -i notify || true")
    if out:
        print("OK: notifyid activity seen in logs")
    else:
        print("WARN: notifyid not visible in logs (may need tracing)")


# ─────────────────────────────────────────────
# STEP 7: virtio_rpmsg_scan channel(Name Service)
# ─────────────────────────────────────────────
def check_rpmsg_devices():
    print("virtio_rpmsg_bus scan and register channel")
    devices = glob.glob("/sys/bus/rpmsg/devices/*")
    if not devices:
        print("WARNING: no rpmsg devices is created")
        return
    print(f"OK: rpmsg devices present: {devices}")
    return devices


# ─────────────────────────────────────────────
# MASTER FLOW
# ─────────────────────────────────────────────
def main():
    print("=== RPMsg / remoteproc runtime validation ===")

    if check_remoteproc() == FAIL:
        return

    check_mailbox()

    virtio = check_virtio_device()
    if not virtio:
        return

    check_rpmsg_transport(virtio)

    check_notifyid_runtime()

    rpmsg = check_rpmsg_devices()

    print("=== ALL CHECKS PASSED ===")


if __name__ == "__main__":
    main()
