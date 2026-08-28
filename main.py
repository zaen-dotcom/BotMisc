"""
╔══════════════════════════════════════════════════════════════════════╗
║  🎮 BOTMISC — Universal Multi-Platform Auto Hunter CLI              ║
║  Compatible with Windows, Linux, and Android Termux                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import argparse

# Ensure UTF-8 output stream
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import BASE_DIR
from database import Database
from auth import TokenManager
from client import NakamaClient
from hunter import AutoHunter
from notifier import Notifier, Colors, RARITY_COLORS


def print_spots_table(db: Database):
    spots = db.get_all_spots()
    if not spots:
        print(f"\n{Colors.YELLOW}[!] Belum ada spot hunting di data/spots.json.{Colors.RESET}\n")
        return

    print(f"\n{Colors.CYAN}{Colors.BOLD}+-----+--------------------+---------+--------+-------------------------+----------+")
    print(f"| No  | Region / Zone      | Obj ID  | Status | Target Miscrit          | Rarity   |")
    print(f"+-----+--------------------+---------+--------+-------------------------+----------+{Colors.RESET}")

    for idx, s in enumerate(spots, 1):
        reg_zone = f"{s.get('region')} {s.get('zone')}"
        obj_id = s.get("object_id")
        status = f"{Colors.GREEN}AKTIF{Colors.RESET}" if s.get("enabled", True) else f"{Colors.DIM}OFF{Colors.RESET}"
        t_name = s.get("target_name", "?")
        t_rar = s.get("target_rarity", "Common")
        rc = RARITY_COLORS.get(t_rar, Colors.WHITE)

        print(f"| {idx:<3d} | {reg_zone:<18s} | #{obj_id:<6d} | {status:<12s} | {t_name:<23s} | {rc}{t_rar:<8s}{Colors.RESET} |")

    print(f"{Colors.CYAN}{Colors.BOLD}+-----+--------------------+---------+--------+-------------------------+----------+{Colors.RESET}\n")


def manage_spots_menu(db: Database):
    while True:
        print_spots_table(db)
        print(f"{Colors.BOLD}Pilihan Pengelolaan Spot:{Colors.RESET}")
        print("  1. Toggle Aktif/Nonaktifkan Spot (Ketik nomor spot)")
        print("  2. Tambah Spot Baru")
        print("  3. Kembali ke Menu Utama")
        
        choice = input(f"\n{Colors.CYAN}Pilih menu [1-3] atau nomor spot: {Colors.RESET}").strip()
        if choice in ("3", "q", "exit", ""):
            break
        elif choice == "2":
            try:
                print(f"\n{Colors.BOLD}-- Tambah Spot Baru --{Colors.RESET}")
                region = input("Region (misal: Forest / Moon / Cave): ").strip() or "Forest"
                zone = input("Zone (misal: Zone 4): ").strip() or "Zone 4"
                obj_id = int(input("ObjectID (angka): ").strip())
                target_name = input("Nama Target Miscrit: ").strip()
                
                m_info = db.find_miscrit_by_name(target_name)
                target_id = m_info["id"] if m_info else 0
                target_rar = m_info["rarity"] if m_info else "Exotic"
                actual_name = m_info["name"] if m_info else target_name

                db.add_spot(region, zone, obj_id, actual_name, target_id, target_rar)
                Notifier.success(f"Spot {actual_name} (#{obj_id}) berhasil ditambahkan!")
            except Exception as e:
                Notifier.error(f"Gagal menambah spot: {e}")
        else:
            try:
                idx = int(choice) - 1
                if db.toggle_spot(idx):
                    Notifier.success(f"Status spot #{choice} berhasil diubah!")
                else:
                    Notifier.warn("Nomor spot tidak valid.")
            except ValueError:
                Notifier.warn("Input tidak dikenali.")


def search_miscrit_menu(db: Database):
    while True:
        q = input(f"\n{Colors.CYAN}Masukkan nama Miscrit yang dicari (atau Enter untuk kembali): {Colors.RESET}").strip()
        if not q:
            break
        info = db.find_miscrit_by_name(q)
        if info:
            mid = info["id"]
            name = info["name"]
            rar = info["rarity"]
            elem = info["element"]
            locs = info.get("locations", {})
            rc = RARITY_COLORS.get(rar, Colors.WHITE)

            print(f"\n{Colors.BOLD}-- Detail Miscrit --{Colors.RESET}")
            print(f"  Nama    : {rc}{name}{Colors.RESET} (#{mid})")
            print(f"  Rarity  : {rc}{rar}{Colors.RESET}")
            print(f"  Element : {elem}")
            print(f"  Lokasi  : {locs}")
        else:
            Notifier.warn(f"Miscrit dengan nama '{q}' tidak ditemukan di database.")


def manage_account_menu(token_mgr: TokenManager):
    cur_user = token_mgr.username or "(Belum Login)"
    print(f"\n{Colors.CYAN}{Colors.BOLD}==================================================")
    print(f"              PENGATURAN AKUN LOGIN               ")
    print(f"=================================================={Colors.RESET}")
    print(f"  Akun Saat Ini: {Colors.GREEN}{cur_user}{Colors.RESET}")
    print("  1. Ganti Akun / Login Ulang")
    print("  2. Hapus Info Login (Logout)")
    print("  3. Kembali ke Menu Utama")
    
    choice = input(f"\n{Colors.CYAN}Pilih opsi [1-3]: {Colors.RESET}").strip()
    if choice == "1":
        token_mgr.prompt_credentials(force=True)
        token_mgr.get_token(force_refresh=True)
    elif choice == "2":
        token_mgr.logout()


def test_connection_menu(token_mgr: TokenManager, client: NakamaClient):
    print(f"\n{Colors.CYAN}[*] Menguji Autentikasi dan Koneksi WebSocket...{Colors.RESET}")
    token = token_mgr.get_token(force_refresh=True)
    if token:
        Notifier.success("Autentikasi HTTP Sukses!")
        if client.connect():
            Notifier.success("WebSocket Nakama Berhasil Terhubung!")
            client.disconnect()
        else:
            Notifier.error("Koneksi WebSocket Gagal.")
    else:
        Notifier.error("Autentikasi HTTP Gagal.")


def select_region_and_start_hunting(db: Database, hunter: AutoHunter):
    while True:
        forest_spots = len(db.get_enabled_spots("Forest"))
        print(f"\n{Colors.CYAN}{Colors.BOLD}==================================================")
        print(f"             PILIH REGION HUNTING                 ")
        print(f"=================================================={Colors.RESET}")
        print(f"  1. 🌲 {Colors.GREEN}{Colors.BOLD}Forest{Colors.RESET} ({forest_spots} Spot Exotic & Legendary Aktif)")
        print(f"  2. 🌙 {Colors.DIM}Moon [SOON]{Colors.RESET}")
        print(f"  3. 🏖️  {Colors.DIM}Sunfall Shores [SOON]{Colors.RESET}")
        print(f"  4. ⛰️  {Colors.DIM}Mount Gemma [SOON]{Colors.RESET}")
        print(f"  5. 🕳️  {Colors.DIM}Caves [SOON]{Colors.RESET}")
        print(f"  6. 🏚️  {Colors.DIM}Haunted Shack [SOON]{Colors.RESET}")
        print(f"  7. 🌴 {Colors.DIM}Miscrian Jungle [SOON]{Colors.RESET}")
        print(f"  8. 🏛️  {Colors.DIM}Temple of Sun [SOON]{Colors.RESET}")
        print(f"  9. 🌋 {Colors.DIM}Volcano [SOON]{Colors.RESET}")
        print(f"  0. ↩️  Kembali ke Menu Utama")
        print(f"{Colors.CYAN}{Colors.BOLD}=================================================={Colors.RESET}")

        choice = input(f"{Colors.CYAN}Pilih Region [0-9]: {Colors.RESET}").strip()

        if choice == "1":
            hunter.start(region="Forest")
            break
        elif choice in ("0", "q", "exit", ""):
            break
        elif choice in ("2", "3", "4", "5", "6", "7", "8", "9"):
            region_names = {
                "2": "Moon",
                "3": "Sunfall Shores",
                "4": "Mount Gemma",
                "5": "Caves",
                "6": "Haunted Shack",
                "7": "Miscrian Jungle",
                "8": "Temple of Sun",
                "9": "Volcano"
            }
            reg = region_names.get(choice, "Region")
            print()
            Notifier.warn(f"Region '{reg}' masih dalam tahap pemetaan dan akan tersedia pada update berikutnya!")
            input(f"{Colors.DIM}Tekan Enter untuk kembali...{Colors.RESET}")
        else:
            Notifier.warn("Pilihan tidak valid.")


def interactive_menu(db: Database, token_mgr: TokenManager, client: NakamaClient, hunter: AutoHunter):
    while True:
        enabled_count = len(db.get_enabled_spots())
        cur_user = token_mgr.username or "Login Diperlukan"
        print(f"\n{Colors.CYAN}{Colors.BOLD}========================================================")
        print(f"            [BOTMISC] MAIN CONTROL PANEL               ")
        print(f"========================================================{Colors.RESET}")
        print(f"  👤 Akun Aktif: {Colors.GREEN}{cur_user}{Colors.RESET}")
        print(f"--------------------------------------------------------")
        print(f"  1. [START] {Colors.GREEN}{Colors.BOLD}Mulai Auto Hunting ({enabled_count} Spot Aktif){Colors.RESET}")
        print(f"  2. [SPOTS] Kelola Hunting Spots (Enable / Disable / Tambah)")
        print(f"  3. [SEARCH] Cari Data Miscrit di Database")
        print(f"  4. [ACCOUNT] Ganti / Kelola Akun Login")
        print(f"  5. [TEST] Uji Koneksi & Token Nakama")
        print(f"  6. [EXIT] Keluar")
        print(f"{Colors.CYAN}{Colors.BOLD}========================================================{Colors.RESET}")

        choice = input(f"{Colors.CYAN}Pilih opsi [1-6]: {Colors.RESET}").strip()

        if choice == "1":
            select_region_and_start_hunting(db, hunter)
        elif choice == "2":
            manage_spots_menu(db)
        elif choice == "3":
            search_miscrit_menu(db)
        elif choice == "4":
            manage_account_menu(token_mgr)
        elif choice == "5":
            test_connection_menu(token_mgr, client)
        elif choice in ("6", "q", "exit"):
            print(f"\n{Colors.YELLOW}Sampai jumpa! Selamat berburu miscrit!{Colors.RESET}\n")
            break


def main():
    parser = argparse.ArgumentParser(description="BotMisc — Universal Auto Hunter CLI for Miscrits")
    parser.add_argument("--start", action="store_true", help="Langsung mulai auto hunting tanpa menu")
    parser.add_argument("--spots", action="store_true", help="Tampilkan daftar spot hunting aktif")
    parser.add_argument("--test", action="store_true", help="Uji koneksi ke server Nakama")
    parser.add_argument("--login", action="store_true", help="Input / Ganti akun login")
    parser.add_argument("--logout", action="store_true", help="Hapus info akun login tersimpan")
    args = parser.parse_args()

    # Initialize Core Components
    db = Database()
    token_mgr = TokenManager()
    client = NakamaClient(token_mgr)
    hunter = AutoHunter(db, token_mgr, client)

    if args.login:
        token_mgr.prompt_credentials(force=True)
        token_mgr.get_token(force_refresh=True)
    elif args.logout:
        token_mgr.logout()
    elif args.start:
        hunter.start()
    elif args.spots:
        print_spots_table(db)
    elif args.test:
        test_connection_menu(token_mgr, client)
    else:
        interactive_menu(db, token_mgr, client, hunter)


if __name__ == "__main__":
    main()
