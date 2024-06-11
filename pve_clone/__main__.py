import re
import subprocess

import serial.tools.list_ports
from ch9329.config import get_serial_number
from serial import Serial


def find_all_cameras():
    print("Searching for camera devices...")
    camera_map: dict[str, tuple[str, str]] = {}
    res = subprocess.run(
        ["dmesg"], text=True, stdout=subprocess.PIPE, check=True
    )
    for l in res.stdout.splitlines():
        match = re.search(
            r"usb (.+): Found UVC 1\.00 device (.+) \(345f:2130\)", l
        )
        if match is not None:
            location, name = match.groups()
            camera_map[name] = name, location
            print(f"Found {name} {location}")
    cameras = list(camera_map.values())
    print(f"{len(cameras)} cameras found.")
    return cameras


def find_all_input_devices():
    print("Searching for ch9329 devices...")
    ch9329_devices: list[tuple[str, str]] = []
    for i in serial.tools.list_ports.comports():
        try:
            if not i.location:
                continue
            if i.vid == 6790 and i.pid == 29987:
                ser = Serial(i.device, 9600, timeout=0.05)
                serial_number = get_serial_number(ser)
                print(f"Found {serial_number} {i.location}")
                ch9329_devices.append((serial_number, i.location))
        except:
            continue
    print(f"{len(ch9329_devices)} input devices found.")
    return ch9329_devices


def find_next_vm_id():
    res = subprocess.run(
        ["pvesh", "get", "/cluster/nextid"],
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )
    return res.stdout.strip()


def main():
    cameras = find_all_cameras()
    inputs = find_all_input_devices()

    print("Searching for pairs...")
    pairs: list[tuple[str, str, str, str]] = []
    for c_name, c_location in cameras:
        if c_name == "USB3 Video":
            continue
        for i_name, i_location in inputs:
            c_name_digits = re.sub(r"[^\d]", "", c_name)
            if c_name_digits in i_name:
                pairs.append((c_name, c_location, i_name, i_location))
    pairs.sort(key=lambda p: int(re.sub(r"[^\d]", "", p[0])))
    for p in pairs:
        print(f"{p[0]} {p[1]:9} {p[2]} {p[3]:9}")
    print(f"{len(pairs)} pairs found.")

    mother_vm = input("Mother VM ID: ")
    vm_count = int(input("Number of VMs to clone: "))
    per_vm = int(input("Number of device pairs per VM: "))
    ignore = input("Devices to ignore: ").strip().split(",")
    ignore = [i.strip() for i in ignore if i.strip()]
    pairs = [p for p in pairs if not any([i in p[0] for i in ignore])]

    if vm_count * per_vm > len(pairs):
        print("Not enough devices.")
        return

    for i in range(vm_count):
        devices = pairs[i * per_vm : i * per_vm + per_vm]
        print("Cloning...")
        start = re.sub(r"[^\d]", "", devices[0][0])
        end = re.sub(r"[^\d]", "", devices[-1][0])
        vm_name = start + "-" + end
        new_vm = find_next_vm_id()
        subprocess.run(
            ["qm", "clone", mother_vm, new_vm, "--name", vm_name], check=True
        )
        i = 0
        for c_name, c_location, i_name, i_location in devices:
            print(f"Adding camera USB device: {c_name} {c_location}")
            cmd = [
                "qm",
                "set",
                new_vm,
                f"-usb{i}",
                f"host={c_location},usb3=no",
            ]
            subprocess.run(cmd, check=True)
            i += 1
            print(f"Adding input USB device: {i_name} {i_location}")
            cmd = [
                "qm",
                "set",
                new_vm,
                f"-usb{i}",
                f"host={i_location}",
            ]
            subprocess.run(cmd, check=True)
            i += 1


if __name__ == "__main__":
    main()
