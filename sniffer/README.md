# ⚔️ Advanced Battle & Capture Protocol Sniffer

Tool MITM khusus untuk merekam, mendekode, dan membedah paket jaringan pertarungan di game Miscrits (*OpCodes*, *Ability Cast*, *Damage Calculation*, dan *Capture/Trap Item*).

---

## 🎯 Tujuan Penggunaan

Gunakan sniffer ini untuk mendapatkan **format paket persis** saat:
1. ⚡ **Menyerang / Cast Skill** (`op_code: 1`)
2. 🔄 **Mengganti Miscrit** (`op_code: 2`)
3. 📦 **Menangkap Miscrit / Menggunakan Trap** (`op_code: 3`)
4. 🏃 **Kabur / Flee** (`op_code: 4`)

Setiap kali Anda melakukan aksi di game, sniffer akan **otomatis menampilkan kode Python siap pakai** yang bisa langsung di-copy ke bot Anda!

---

## 🚀 Cara Menjalankan

Buka terminal dan jalankan perintah berikut:

```powershell
cd D:\Miscrits\Miscrits_File\BotMisc\mitm_sniffer
mitmdump -s battle_sniffer.py --ssl-insecure
```

---

## 📋 Langkah Pengujian di Game:

1. **Jalankan sniffer** di terminal.
2. **Buka game Miscrits** (pastikan proxy aktif).
3. **Masuk ke pertarungan wild miscrit**.
4. **Lakukan 3 hal ini di dalam pertarungan:**
   * **Klik Serangan / Skill:** Terminal akan menampilkan `OpCode: 1` beserta ID skill yang dipakai.
   * **Klik Tangkap / Gunakan Item Trap:** Terminal akan menampilkan `OpCode: 3` beserta ID item/crate capture.
   * **Perhatikan Respon Server:** Terminal akan menampilkan status apakah tangkapan berhasil (*Captured*) atau lepas (*Broke Free*).
5. **Lihat Output JSON Lengkap:**
   Seluruh riwayat pertarungan otomatis tersimpan rapi di folder:
   📁 `BotMisc/mitm_sniffer/captured_battles/`
