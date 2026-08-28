# 🎮 BotMisc — Universal Miscrits Auto Hunter (Full CLI)

Bot auto-hunting berbasis Command Line Interface (CLI) super ringan, modular, dan kompatibel 100% di **Windows**, **Linux**, dan **Android (Termux)**.

---

## 🌟 Fitur Utama

- 🔄 **Multi-Spot Rotation (Zero Cooldown Waste):** 
  Setelah kabur (*flee*) dari suatu objek, server Nakama mengaktifkan *per-object cooldown* ~15 detik. Bot ini secara cerdas merotasi penyerangan ke seluruh spot **Exotic & Legendary** lain dalam siklus (Spot 1 ➔ Spot 2 ➔ Spot 3 ➔ Spot 4 ➔ Spot 5 ➔ Spot 6 ➔ Spot 1), sehingga saat kembali ke Spot 1, cooldown-nya sudah selesai.
- 🎯 **Target Harian (Exotic & Legendary):** Fokus farming hewan yang spawn setiap hari.
- 🔊 **Cross-Platform Alarm:** Berbunyi saat Bingo di Windows (`winsound`), Termux (`termux-vibrate` & `termux-notification`), dan Linux (`terminal bell` / `aplay`).
- 📱 **Termux Ready:** Tidak ada dependency GUI (seperti tkinter), bisa dijalankan 24/7 di HP Android via Termux atau VPS Linux.
- 🧩 **Arsitektur Modular:** Kode terpisah rapi menjadi modul konfigurasi, auth, websocket client, database, notifier, dan hunting engine.

---

## 📁 Struktur Folder Project

```
BotMisc/
├── config.py             # Pengaturan endpoint, auth payload, dan delay
├── auth.py               # Manager login JWT & auto-refresh token
├── client.py             # WebSocket RPC Nakama & protocol battle/flee
├── database.py           # Loader master database 393 Miscrits
├── hunter.py             # Engine rotasi multi-spot & deteksi target
├── notifier.py           # Formatter warna terminal & alarm cross-platform
├── main.py               # Entrypoint CLI & menu interaktif
├── requirements.txt      # Dependency (websocket-client, requests, colorama)
└── data/
    ├── spots.json        # Daftar spot hunting aktif
    └── miscrits.json     # Master database 393 Miscrits
```

---

## 🚀 Cara Menjalankan

### 1. Di Windows:
```powershell
cd D:\Miscrits\Miscrits_File\BotMisc
pip install -r requirements.txt
python main.py
```

### 2. Di Linux / VPS:
```bash
cd BotMisc
pip3 install -r requirements.txt
python3 main.py
```

### 3. Di Android (Termux):
```bash
pkg update && pkg install python
cd BotMisc
pip install -r requirements.txt
python main.py
```

---

## ⚡ Perintah Cepat (Command-Line Arguments)

| Perintah | Deskripsi |
|---|---|
| `python main.py` | Buka Menu Interaktif |
| `python main.py --start` | Langsung mulai farming (Cocok untuk background / tmux / cron) |
| `python main.py --spots` | Tampilkan daftar spot hunting aktif |
| `python main.py --test` | Uji koneksi & login akun |

---

## 🎯 Daftar Spot Bawaan (Forest Region):

1. **Forest Zone 2 (ID 63):** ⭐ `Blighted Cubsprout` [Exotic]
2. **Forest Zone 3 (ID 96):** ⭐ `Mama` [Exotic]
3. **Forest Zone 3 (ID 98):** ⭐ `Defilio` [Exotic]
4. **Forest Zone 4 (ID 96):** ⭐ `Dark Nessy` [Exotic]
5. **Forest Zone 4 (ID 98):** 👑 `Blighted Flowerpiller` [Legendary]
6. **Forest Zone 4 (ID 99):** 👑 `Blighted Flue` [Legendary]
