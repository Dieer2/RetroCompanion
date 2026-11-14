"""Mock RetroArch network command server for testing."""
import socket, sys, json, threading
class Mock:
    def __init__(self, port, mode="memory"):
        self.ram = bytearray(0x8000); self.mode = mode
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.s.bind(("127.0.0.1", port))
        threading.Thread(target=self.loop, daemon=True).start()
    def loop(self):
        while True:
            d, a = self.s.recvfrom(4096); p = d.decode().split()
            if p[0] == "GET_STATUS": self.s.sendto(getattr(self, "status", b"GET_STATUS PLAYING nes,Dragon Warrior (USA),crc32=caaf5c6b\n"), a)
            elif p[0] in ("READ_CORE_MEMORY", "READ_CORE_RAM"):
                if p[0] == "READ_CORE_MEMORY" and self.mode == "ramonly":
                    self.s.sendto(("READ_CORE_MEMORY %s -1 no memory map defined\n" % p[1]).encode(), a); continue
                ad, n = int(p[1], 16), int(p[2])
                self.s.sendto(("%s %x %s\n" % (p[0], ad, " ".join("%02x" % b for b in self.ram[ad:ad+n]))).encode(), a)
def setram(ram, **k):
    m = dict(x=0x3A, y=0x3B, map=0x45, equip=0xBE, keys=0xBF, herbs=0xC0, hp=0xC5, mp=0xC6, level=0xC7,
             maxhp=0xCA, maxmp=0xCB, mods=0xCF, pflags=0xDF, story=0xE4, str=0xC8, agi=0xC9, atk=0xCC, dfn=0xCD, spells=0xCE, en_id=0xE0, en_hp=0xE2, chr=0x6003)
    for key, v in k.items():
        if key == "exp": ram[0xBA], ram[0xBB] = v & 255, v >> 8
        elif key == "gold": ram[0xBC], ram[0xBD] = v & 255, v >> 8
        elif key == "items":
            v = list(v) + [0]*(8-len(v))
            for i in range(4): ram[0xC1+i] = v[2*i] | (v[2*i+1] << 4)
        elif key == "en_stats": ram[0x100:0x108] = bytes(v)
        else: ram[m[key]] = v
