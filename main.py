import subprocess
from tkinter import Tk, filedialog, ttk, messagebox, TclError
import tkinter as tk
from pathlib import Path
import shutil
import json
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# ==================== CONSTANTS ====================
class Offsets(Enum):
    """Game offset constants"""
    AMRITA = 0x7B8D0
    GOLD = 0x7B8D8
    PLAYER_LEVEL = 0x1C4904
    CONSTITUTION = 0x1C490C
    HEART = 0x1C4910
    COURAGE = 0x1C4928
    STAMINA = 0x1C4914
    STRENGTH = 0x1C4918
    SKILL = 0x1C491C
    DEXTERITY = 0x1C4920
    MAGIC = 0x1C4924
    NINJITSU = 0x1C4B58
    ONMYO = 0x1C4B64
    SWORD = 0x1C4A8C
    DUAL_SWORD = 0x1C4A98
    AXE = 0x1C4AB0
    KUSARIGAMA = 0x1C4ABC
    ODACHI = 0x1C4AC8
    TONFA = 0x1C4AD4
    HATCHET = 0x1C4AE0
    WEAPON_START = 0xED508
    ITEM_START = 0x105EC8
    SCROLL_START = 0x294080
    # Integrity check offsets
    INTEGRITY_CHECK_1 = 0x7B882 + 0x158
    INTEGRITY_CHECK_2 = 0x7B884 + 0x158
    INTEGRITY_CHECK_3 = 0x7B7E4 + 0x158
    INTEGRITY_CHECK_4 = 0xECF4A + 0x158
    # PS4 padding
    PS4_PADDING = 0x148
    # Import offsets
    CHARACTER_DATA_START = 0x178
    EXPECTED_FILE_SIZE = 0x296F28

class InventorySize(Enum):
    """Inventory size constants"""
    WEAPON_SIZE = 0x90
    WEAPON_SLOTS = 700
    ITEM_SIZE = 0x88
    ITEM_SLOTS = 900
    SCROLL_SIZE = 0x88
    SCROLL_SLOTS = 248

# ==================== DATA MODELS ====================
@dataclass
class SaveState:
    """Encapsulated save state to replace global variables"""
    data: bytearray = field(default_factory=bytearray)
    mode: Optional[str] = None
    decrypted_path: Path = field(default_factory=Path)
    decrypted: bool = False
    weapons: List[Dict] = field(default_factory=list)
    items: List[Dict] = field(default_factory=list)
    scrolls: List[Dict] = field(default_factory=list)

@dataclass
class ImportState:
    """Encapsulated import state"""
    data: bytearray = field(default_factory=bytearray)
    mode: Optional[str] = None
    decrypted_path: Path = field(default_factory=Path)
    decrypted: bool = False

# Global state instances (to be replaced incrementally)
save_state = SaveState()
import_state = ImportState()
APP_INSTANCE = None

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

base_dir = get_base_dir()
config_file = base_dir / "editor_config.json"
AUTO_LOAD_LAST_SAVE = True
SHOW_LOAD_SUCCESS_POPUP = False
LEFT_PANEL_MIN_WIDTH = 400

def resource_path(*parts: str) -> Path:
    return base_dir.joinpath(*parts)

def get_stat_definitions() -> List[Tuple[str, int, int]]:
    """Return stat name, offset, byte_size tuples"""
    return [
        ("Amrita", Offsets.AMRITA.value, 8),
        ("Gold", Offsets.GOLD.value, 8),
        ("Level", Offsets.PLAYER_LEVEL.value, 2),
        ("Constitution", Offsets.CONSTITUTION.value, 2),
        ("Heart", Offsets.HEART.value, 2),
        ("Courage", Offsets.COURAGE.value, 2),
        ("Stamina", Offsets.STAMINA.value, 2),
        ("Strength", Offsets.STRENGTH.value, 2),
        ("Skill", Offsets.SKILL.value, 2),
        ("Dexterity", Offsets.DEXTERITY.value, 2),
        ("Magic", Offsets.MAGIC.value, 2),
        ("Ninjutsu", Offsets.NINJITSU.value, 4),
        ("Onmyo", Offsets.ONMYO.value, 4),
        ("Sword", Offsets.SWORD.value, 4),
        ("Dual Sword", Offsets.DUAL_SWORD.value, 4),
        ("Axe", Offsets.AXE.value, 4),
        ("Kusarigama", Offsets.KUSARIGAMA.value, 4),
        ("Odachi", Offsets.ODACHI.value, 4),
        ("Tonfa", Offsets.TONFA.value, 4),
        ("Hatchet", Offsets.HATCHET.value, 4),
    ]

# ==================== BINARY SCHEMA DEFINITIONS ====================
# Define schemas for DRY parsing/writing
WEAPON_SCHEMA = [
    ("item_id_1", 2),
    ("Refashion", 2),
    ("quantity", 2),
    ("weapon_level", 2),
    ("weapon_level_start", 2),
    ("Higher_Level_Modifier", 2),
    ("fam", 4),
    ("left_right_1", 1),
    ("left_right_2", 1),
    ("left_right_3", 1),
    ("left_right_4", 1),
    ("weapon_tier", 1),
    ("left_right_5", 1),
    ("left_right_6", 1),
    ("left_right_7", 1),
    ("yokai_weapon_gauge", 2),
    ("rcmd_level", 2),
    ("empty_1", 2),
    ("remodel_type", 1),
    ("attempt_remaining", 1),
    ("extra_1", 16),
]

EFFECT_SCHEMA = [
    ("effect_id_{}", 4),
    ("effect_magnitude_{}", 4),
    ("effect_footer_part1_{}", 2),
    ("effect_footer_part2_{}", 2),
]

WEAPON_FOOTER_SCHEMA = [
    ("empty_2", 4),
    ("is_equiped", 1),
    ("empty_3", 7),
]

ITEM_SCHEMA = [
    ("item_id_1", 2),
    ("Refashion", 2),
    ("quantity", 2),
]

SCROLL_SCHEMA = [
    ("item_id_1", 2),
    ("item_id_2", 2),
    ("item_id_3", 2),
    ("item_level_1", 2),
    ("item_level_2", 2),
    ("higher_level_mod", 2),
    ("unk_1", 4),
    ("extra_1", 2),
    ("is_it_locked", 1),
    ("extra_2", 1),
    ("tier", 1),
    ("unk_2", 1),
    ("unk_3", 9),
    ("attempts_remaining", 1),
    ("unk_4", 16),
]

SCROLL_FOOTER_SCHEMA = [
    ("extra_3", 4),
]

# Editor field definitions
EDITOR_FIELDS = {
    "weapon": [
        ("item_id_1", "Item ID"),
        ("Refashion", "Refashion"),
        ("quantity", "Quantity"),
        ("weapon_level", "Level"),
        ("weapon_level_start", "Level Start"),
        ("Higher_Level_Modifier", "Higher Level"),
        ("fam", "Familiarity"),
        ("weapon_tier", "Tier"),
        ("yokai_weapon_gauge", "Yokai Gauge"),
        ("rcmd_level", "Recommended Level"),
        ("remodel_type", "Remodel Type"),
        ("attempt_remaining", "Attempts Remaining"),
    ],
    "item": [
        ("item_id_1", "Item ID"),
        ("Refashion", "Refashion"),
        ("quantity", "Quantity"),
    ],
    "scroll": [
        ("item_id_1", "Item ID"),
        ("item_id_2", "Item ID 2"),
        ("item_id_3", "Item ID 3"),
        ("item_level_1", "Level 1"),
        ("item_level_2", "Level 2"),
        ("higher_level_mod", "Higher Level Mod"),
        ("tier", "Tier"),
        ("is_it_locked", "Locked"),
        ("attempts_remaining", "Attempts"),
    ],
}

# ==================== CONFIG MANAGEMENT ====================
class ConfigManager:
    """Manage application configuration and preferences"""
    
    @staticmethod
    def load_config() -> Dict:
        """Load config from file or return defaults"""
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except:
                return ConfigManager.get_defaults()
        return ConfigManager.get_defaults()
    
    @staticmethod
    def get_defaults() -> Dict:
        return {
            "panel_widths": {"weapon": LEFT_PANEL_MIN_WIDTH, "item": LEFT_PANEL_MIN_WIDTH, "scroll": LEFT_PANEL_MIN_WIDTH},
            "window_geometry": "1400x800",
            "last_save_path": ""
        }
    
    @staticmethod
    def save_config(config: Dict):
        """Save config to file"""
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass

# ==================== JSON MANAGEMENT ====================
class JSONManager:
    """Handle JSON file loading"""
    _items_cache: Optional[Dict] = None
    _effects_cache: Optional[List] = None
    
    @classmethod
    def load_items(cls) -> Dict:
        if cls._items_cache is None:
            with open(resource_path("items.json"), "r") as f:
                cls._items_cache = json.load(f)
        assert cls._items_cache is not None
        return cls._items_cache
    
    @classmethod
    def load_effects(cls) -> List:
        if cls._effects_cache is None:
            with open(resource_path("effects.json"), "r") as f:
                cls._effects_cache = json.load(f)
        assert cls._effects_cache is not None
        return cls._effects_cache
    
    @classmethod
    def get_effect_dropdown_list(cls) -> List[str]:
        effects = cls.load_effects()
        return [f"{entry['id']} - {entry['Effect']}" for entry in effects]
    
    @classmethod
    def get_item_name_type(cls, item_id_hex: str) -> Tuple[str, str]:
        items_json = cls.load_items()
        if item_id_hex in items_json:
            info = items_json[item_id_hex]
            return info.get("name", "Unknown"), info.get("type", "?")
        return "Unknown", "?"

# ==================== UTILITY FUNCTIONS ====================
def find_value_at_offset(section_data: bytearray, offset: int, byte_size: int) -> Optional[int]:
    """Extract value from binary data at offset"""
    try:
        value_bytes = section_data[offset:offset+byte_size]
        return int.from_bytes(value_bytes, 'little') if len(value_bytes) == byte_size else None
    except IndexError:
        return None

def write_le(value: int, length: int) -> bytes:
    """Convert integer to little-endian bytes"""
    if isinstance(value, int):
        return value.to_bytes(length, 'little')
    elif isinstance(value, (bytes, bytearray)):
        if len(value) != length:
            raise ValueError(f"Expected {length} bytes, got {len(value)}")
        return value
    else:
        raise TypeError(f"Cannot convert type {type(value)} to bytes")

def swap_endian_hex(val: int) -> str:
    """Convert item_id to hex string with endian swap"""
    return f"{((val & 0xFF) << 8) | (val >> 8):04X}"

# ==================== BINARY PARSING REFACTORED ====================
class BinaryParser:
    """Generic binary data parser using schemas"""
    
    @staticmethod
    def parse_struct(data: bytearray, offset: int, schema: List[Tuple[str, int]]) -> Dict[str, int]:
        """Parse binary data using a schema definition"""
        result = {}
        o = offset
        for field_name, size in schema:
            result[field_name] = int.from_bytes(data[o:o+size], 'little')
            o += size
        return result
    
    @staticmethod
    def parse_effects(data: bytearray, offset: int, num_effects: int = 7) -> Tuple[Dict[str, int], int]:
        """Parse effect fields"""
        result = {}
        o = offset
        for i in range(1, num_effects + 1):
            result[f'effect_id_{i}'] = int.from_bytes(data[o:o+4], 'little')
            o += 4
            result[f'effect_magnitude_{i}'] = int.from_bytes(data[o:o+4], 'little')
            o += 4
            result[f'effect_footer_part1_{i}'] = int.from_bytes(data[o:o+2], 'little')
            o += 2
            result[f'effect_footer_part2_{i}'] = int.from_bytes(data[o:o+2], 'little')
            o += 2
        return result, o
    
    @staticmethod
    def write_struct(data: bytearray, offset: int, item: Dict[str, Any], schema: List[Tuple[str, int]]) -> int:
        """Write binary data using a schema definition"""
        o = offset
        for field_name, size in schema:
            data[o:o+size] = write_le(item[field_name], size)
            o += size
        return o
    
    @staticmethod
    def write_effects(data: bytearray, offset: int, item: Dict[str, Any], num_effects: int = 7) -> int:
        """Write effect fields"""
        o = offset
        for i in range(1, num_effects + 1):
            data[o:o+4] = write_le(item[f'effect_id_{i}'], 4)
            o += 4
            data[o:o+4] = write_le(item[f'effect_magnitude_{i}'], 4)
            o += 4
            data[o:o+2] = write_le(item[f'effect_footer_part1_{i}'], 2)
            o += 2
            data[o:o+2] = write_le(item[f'effect_footer_part2_{i}'], 2)
            o += 2
        return o

# ==================== ENCRYPTION/DECRYPTION ====================
class SaveCrypto:
    """Handle save file encryption/decryption operations"""
    
    @staticmethod
    def decrypt_pc(file_path: str, exe_path: Path) -> bytearray:
        """Decrypt PC save file"""
        subprocess.run(
            [str(exe_path), file_path],
            cwd=exe_path.parent,
            input="\n",
            text=True,
            capture_output=True
        )
        
        decrypted_path = exe_path.parent / "decr_SAVEDATA.BIN"
        with open(decrypted_path, 'rb') as f:
            return bytearray(f.read())
    
    @staticmethod
    def encrypt_pc(data: bytearray, decrypted_path: Path, exe_path: Path) -> bytes:
        """Encrypt PC save file"""
        with open(decrypted_path, 'wb') as f:
            f.write(data)
        
        subprocess.run(
            [str(exe_path), decrypted_path],
            cwd=exe_path.parent,
            input="\n",
            text=True,
            capture_output=True
        )
        
        encrypted_path = exe_path.parent / "decr_decr_SAVEDATA.BIN"
        with open(encrypted_path, 'rb') as f:
            return f.read()
    
    @staticmethod
    def decrypt_ps4(file_path: str, exe_path: Path) -> Tuple[bytearray, bool, Path]:
        """Decrypt PS4 save file. Returns (data, was_decrypted, path)"""
        dst_path = exe_path.parent / "APP.BIN"
        shutil.copy2(file_path, dst_path)
        
        with open(dst_path, 'rb') as f:
            magic_bytes = f.read(4)
        
        if magic_bytes != b'\x00\x00\x00\x00':
            subprocess.run(
                [str(exe_path), str(dst_path)],
                cwd=exe_path.parent,
                input="\n",
                text=True,
                check=True
            )
            decrypted_path = exe_path.parent / "APP.BIN_out.bin"
            was_decrypted = False
        else:
            decrypted_path = Path(file_path)
            was_decrypted = True
        
        with open(decrypted_path, 'rb') as f:
            data = bytearray(f.read())
        
        return data, was_decrypted, decrypted_path
    
    @staticmethod
    def encrypt_ps4(data: bytearray, decrypted_path: Path, exe_path: Path) -> bytes:
        """Encrypt PS4 save file"""
        with open(decrypted_path, 'wb') as f:
            f.write(data)
        
        subprocess.run(
            [str(exe_path), str(decrypted_path)],
            cwd=exe_path.parent,
            input="\n",
            text=True,
            check=True
        )
        
        encrypted_path = exe_path.parent / "APP.BIN_out.bin_out.bin"
        with open(encrypted_path, 'rb') as f:
            return f.read()
    
    @staticmethod
    def disable_integrity_checks(data: bytearray) -> None:
        """Disable game integrity checks"""
        data[Offsets.INTEGRITY_CHECK_1.value] = 0
        data[Offsets.INTEGRITY_CHECK_2.value] = 0
        data[Offsets.INTEGRITY_CHECK_3.value] = 0
        data[Offsets.INTEGRITY_CHECK_4.value] = 0

# ==================== FILE OPERATIONS ====================
class FileManager:
    """Handle save file loading and encryption/decryption"""
    last_opened_file_path: Optional[Path] = None

    @staticmethod
    def _get_save_target_path() -> Optional[Path]:
        target_path = FileManager.last_opened_file_path
        if target_path is None:
            messagebox.showwarning("Warning", "No save file selected")
            return None
        return target_path
    
    @staticmethod
    def open_file(file_path: Optional[str] = None) -> bool:
        if file_path is None:
            file_path = filedialog.askopenfilename(
                title="Select Save File",
                filetypes=[("Save Files", "*.BIN"), ("All Files", "*.*")]
            )
        if not file_path:
            return False

        selected_path = Path(file_path)
        if not selected_path.exists():
            messagebox.showerror("Error", f"Save file not found: {selected_path}")
            return False

        file_name = Path(file_path).name

        if file_name == 'SAVEDATA.BIN':
            loaded = FileManager._load_pc_save(file_path)
        elif file_name == 'APP.BIN':
            loaded = FileManager._load_ps4_save(file_path)
        else:
            messagebox.showerror("Error", "Unknown file. Use SAVEDATA.BIN (PC) or APP.BIN (PS4)")
            return False

        if loaded:
            FileManager.last_opened_file_path = selected_path
        return loaded
    
    @staticmethod
    def _load_pc_save(file_path: str) -> bool:
        save_state.mode = 'PC'
        exe_path = resource_path("PC", "pc.exe")
        
        save_state.data = SaveCrypto.decrypt_pc(file_path, exe_path)
        save_state.decrypted_path = exe_path.parent / "decr_SAVEDATA.BIN"
        
        SaveCrypto.disable_integrity_checks(save_state.data)
        return True
    
    @staticmethod
    def _load_ps4_save(file_path: str) -> bool:
        save_state.mode = 'PS4'
        exe_path = resource_path("ps4", "ps4.exe")
        
        data, was_decrypted, decrypted_path = SaveCrypto.decrypt_ps4(file_path, exe_path)
        save_state.decrypted = was_decrypted
        save_state.decrypted_path = decrypted_path
        
        # Add padding for PS4
        padding = b'\x00' * Offsets.PS4_PADDING.value
        save_state.data = bytearray(padding) + data
        SaveCrypto.disable_integrity_checks(save_state.data)
        return True
    
    @staticmethod
    def save_file() -> None:
        if not save_state.data:
            messagebox.showwarning("Warning", "No file loaded")
            return

        if APP_INSTANCE is not None and not APP_INSTANCE.commit_active_editor_changes():
            return
        
        InventoryManager.write_all_to_data()
        
        if save_state.mode == 'PC':
            FileManager._save_pc_file()
        elif save_state.mode == 'PS4':
            FileManager._save_ps4_file()
    
    @staticmethod
    def _save_pc_file() -> None:
        target_path = FileManager._get_save_target_path()
        if target_path is None:
            return

        exe_path = base_dir / "pc" / "pc.exe"
        final_data = SaveCrypto.encrypt_pc(save_state.data, save_state.decrypted_path, exe_path)

        with open(target_path, 'wb') as f:
            f.write(final_data)
        
        if APP_INSTANCE is not None:
            APP_INSTANCE.show_status_message(f"Saved to {target_path}")
    
    @staticmethod
    def _save_ps4_file() -> None:
        target_path = FileManager._get_save_target_path()
        if target_path is None:
            return

        ps4_data = save_state.data[Offsets.PS4_PADDING.value:]
        
        if save_state.decrypted:
            with open(target_path, 'wb') as f:
                f.write(ps4_data)
            if APP_INSTANCE is not None:
                APP_INSTANCE.show_status_message(f"Saved to {target_path}")
            return
        
        exe_path = base_dir / "ps4" / "ps4.exe"
        final_data = SaveCrypto.encrypt_ps4(ps4_data, save_state.decrypted_path, exe_path)

        with open(target_path, 'wb') as f:
            f.write(final_data)
        
        if APP_INSTANCE is not None:
            APP_INSTANCE.show_status_message(f"Saved to {target_path}")
    
    @staticmethod
    def open_file_import() -> bool:
        file_path = filedialog.askopenfilename(
            title="Select Save File to Import",
            filetypes=[("Save Files", "*.BIN"), ("All Files", "*.*")]
        )
        if not file_path:
            return False
        
        file_name = Path(file_path).name
        
        if file_name == 'SAVEDATA.BIN':
            import_state.mode = 'PC'
            exe_path = resource_path("PC_import", "pc.exe")
            
            import_state.data = SaveCrypto.decrypt_pc(file_path, exe_path)
            import_state.decrypted_path = exe_path.parent / "decr_SAVEDATA.BIN"
            
            SaveCrypto.disable_integrity_checks(import_state.data)
            return True
        
        elif file_name == 'APP.BIN':
            import_state.mode = 'PS4'
            exe_path = resource_path("PS4_import", "ps4.exe")
            
            data, was_decrypted, decrypted_path = SaveCrypto.decrypt_ps4(file_path, exe_path)
            import_state.decrypted = was_decrypted
            import_state.decrypted_path = decrypted_path
            
            padding = b'\x00' * Offsets.PS4_PADDING.value
            import_state.data = bytearray(padding) + data
            SaveCrypto.disable_integrity_checks(import_state.data)
            return True
        else:
            messagebox.showerror("Error", "Unknown file. Use SAVEDATA.BIN (PC) or APP.BIN (PS4)")
            return False

def import_save():
    if not FileManager.open_file_import():
        return
    
    if not save_state.data:
        messagebox.showerror("Error", "Load your current save first")
        return
    
    if messagebox.askyesno("Confirm", "Replace current character?"):
        save_state.data = save_state.data[:Offsets.CHARACTER_DATA_START.value] + import_state.data[Offsets.CHARACTER_DATA_START.value:]
        if len(save_state.data) != Offsets.EXPECTED_FILE_SIZE.value:
            messagebox.showerror('Error', 'Size mismatch')
        messagebox.showinfo("Success", "File imported. Changes apply on next game load.")

# ==================== INVENTORY PARSING ====================
class InventoryParser:
    """Parse binary inventory data efficiently using schemas"""
    
    @staticmethod
    def parse_weapon(offset: int) -> Dict:
        """Parse weapon data from binary"""
        weapon = BinaryParser.parse_struct(save_state.data, offset, WEAPON_SCHEMA)
        
        # Parse effects
        effects_offset = offset + sum(size for _, size in WEAPON_SCHEMA)
        effects, next_offset = BinaryParser.parse_effects(save_state.data, effects_offset)
        weapon.update(effects)
        
        # Parse footer
        footer = BinaryParser.parse_struct(save_state.data, next_offset, WEAPON_FOOTER_SCHEMA)
        weapon.update(footer)
        
        weapon['offset'] = offset
        return weapon
    
    @staticmethod
    def parse_item(offset: int) -> Dict:
        """Parse item data from binary"""
        item = BinaryParser.parse_struct(save_state.data, offset, ITEM_SCHEMA)
        item['offset'] = offset
        return item
    
    @staticmethod
    def parse_scroll(offset: int) -> Dict:
        """Parse scroll data from binary"""
        scroll = BinaryParser.parse_struct(save_state.data, offset, SCROLL_SCHEMA)
        
        # Parse effects
        effects_offset = offset + sum(size for _, size in SCROLL_SCHEMA)
        effects, next_offset = BinaryParser.parse_effects(save_state.data, effects_offset)
        scroll.update(effects)
        
        # Parse footer
        footer = BinaryParser.parse_struct(save_state.data, next_offset, SCROLL_FOOTER_SCHEMA)
        scroll.update(footer)
        
        scroll['offset'] = offset
        return scroll

class InventoryManager:
    """Manage inventory data efficiently"""
    
    @staticmethod
    def load_weapons() -> None:
        save_state.weapons = []
        for slot in range(InventorySize.WEAPON_SLOTS.value):
            offset = Offsets.WEAPON_START.value + (slot * InventorySize.WEAPON_SIZE.value)
            weapon = InventoryParser.parse_weapon(offset)
            weapon['slot'] = slot
            save_state.weapons.append(weapon)
    
    @staticmethod
    def load_items() -> None:
        save_state.items = []
        for slot in range(InventorySize.ITEM_SLOTS.value):
            offset = Offsets.ITEM_START.value + (slot * InventorySize.ITEM_SIZE.value)
            item = InventoryParser.parse_item(offset)
            item['slot'] = slot
            save_state.items.append(item)
    
    @staticmethod
    def load_scrolls() -> None:
        save_state.scrolls = []
        for slot in range(InventorySize.SCROLL_SLOTS.value):
            offset = Offsets.SCROLL_START.value + (slot * InventorySize.SCROLL_SIZE.value)
            if offset + InventorySize.SCROLL_SIZE.value > len(save_state.data):
                break
            
            if int.from_bytes(save_state.data[offset:offset+2], 'little') == 0:
                continue
            
            scroll = InventoryParser.parse_scroll(offset)
            scroll['slot'] = slot
            save_state.scrolls.append(scroll)
    
    @staticmethod
    def write_all_to_data() -> None:
        InventoryManager.write_weapons_to_data()
        InventoryManager.write_items_to_data()
        InventoryManager.write_scrolls_to_data()
    
    @staticmethod
    def write_weapons_to_data() -> None:
        for weapon in save_state.weapons:
            offset = Offsets.WEAPON_START.value + (weapon['slot'] * InventorySize.WEAPON_SIZE.value)
            
            # Write main fields
            o = BinaryParser.write_struct(save_state.data, offset, weapon, WEAPON_SCHEMA)
            
            # Write effects
            o = BinaryParser.write_effects(save_state.data, o, weapon)
            
            # Write footer
            BinaryParser.write_struct(save_state.data, o, weapon, WEAPON_FOOTER_SCHEMA)
    
    @staticmethod
    def write_items_to_data() -> None:
        for item in save_state.items:
            offset = Offsets.ITEM_START.value + (item['slot'] * InventorySize.ITEM_SIZE.value)
            BinaryParser.write_struct(save_state.data, offset, item, ITEM_SCHEMA)
    
    @staticmethod
    def write_scrolls_to_data() -> None:
        for scroll in save_state.scrolls:
            offset = Offsets.SCROLL_START.value + (scroll['slot'] * InventorySize.SCROLL_SIZE.value)
            
            # Write main fields
            o = BinaryParser.write_struct(save_state.data, offset, scroll, SCROLL_SCHEMA)
            
            # Write effects
            o = BinaryParser.write_effects(save_state.data, o, scroll)
            
            # Write footer
            BinaryParser.write_struct(save_state.data, o, scroll, SCROLL_FOOTER_SCHEMA)

# ==================== CUSTOM WIDGETS ====================
class SearchableCombobox(ttk.Frame):
    """Reusable searchable combobox widget"""
    
    def __init__(self, master=None, values=None, width=40, **kwargs):
        super().__init__(master, **kwargs)
        
        self.full_values = values if values else []
        self.filtered_values = self.full_values.copy()
        
        # Entry
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left", fill="x", expand=True)
        
        # Dropdown button
        self.btn = ttk.Button(self, text="▼", width=2, command=self.toggle_dropdown)
        self.btn.pack(side="right")
        
        # Dropdown frame
        self.listbox_frame = tk.Toplevel(self)
        self.listbox_frame.withdraw()
        self.listbox_frame.overrideredirect(True)
        
        self.listbox = tk.Listbox(self.listbox_frame, height=10, width=width)
        self.listbox.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(self.listbox_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Bindings
        self.var.trace_add("write", self._on_type)
        self.entry.bind("<Down>", self._on_arrow_down)
        self.entry.bind("<Up>", self._on_arrow_up)
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Escape>", self._on_escape)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Return>", self._on_return)
        self.listbox.bind("<Escape>", self._on_escape)
        self.listbox.bind("<Double-Button-1>", self._on_select)
        
        self.dropdown_visible = False
    
    def _on_type(self, *args):
        if getattr(self, '_silent', False):
            return
        typed = self.var.get().lower()
        self.filtered_values = self.full_values.copy() if not typed else [v for v in self.full_values if typed in v.lower()]
        self._update_listbox()
        if not self.dropdown_visible and self.filtered_values:
            self.show_dropdown()
    
    def _update_listbox(self):
        self.listbox.delete(0, tk.END)
        for value in self.filtered_values:
            self.listbox.insert(tk.END, value)
    
    def show_dropdown(self):
        if not self.filtered_values:
            return
        self.dropdown_visible = True
        x, y = self.entry.winfo_rootx(), self.entry.winfo_rooty() + self.entry.winfo_height()
        width = self.entry.winfo_width() + self.btn.winfo_width()
        self.listbox_frame.geometry(f"{width}x200+{x}+{y}")
        self.listbox_frame.deiconify()
        self.listbox_frame.lift()
    
    def hide_dropdown(self):
        self.dropdown_visible = False
        self.listbox_frame.withdraw()
    
    def toggle_dropdown(self):
        if self.dropdown_visible:
            self.hide_dropdown()
        else:
            self.filtered_values = self.full_values.copy()
            self._update_listbox()
            self.show_dropdown()
            self.entry.focus_set()
    
    def _on_arrow_down(self, event):
        if not self.dropdown_visible:
            self.show_dropdown()
        else:
            current = self.listbox.curselection()
            if not current:
                self.listbox.selection_set(0)
            elif current[0] < self.listbox.size() - 1:
                self.listbox.selection_clear(current)
                self.listbox.selection_set(current[0] + 1)
                self.listbox.see(current[0] + 1)
        return "break"
    
    def _on_arrow_up(self, event):
        if self.dropdown_visible:
            current = self.listbox.curselection()
            if current and current[0] > 0:
                self.listbox.selection_clear(current)
                self.listbox.selection_set(current[0] - 1)
                self.listbox.see(current[0] - 1)
        return "break"
    
    def _on_return(self, event):
        if self.dropdown_visible:
            current = self.listbox.curselection()
            if current:
                self.var.set(self.listbox.get(current[0]))
            self.hide_dropdown()
        return "break"
    
    def _on_escape(self, event):
        self.hide_dropdown()
        return "break"
    
    def _on_select(self, event):
        current = self.listbox.curselection()
        if current:
            self.var.set(self.listbox.get(current[0]))
            self.hide_dropdown()
    
    def _on_focus_out(self, event):
        self.after(200, lambda: self.hide_dropdown() if not self.listbox.focus_get() else None)
    
    def get(self):
        return self.var.get()
    
    def set(self, value: str) -> None:
        self.var.set(value)

    def set_silent(self, value: str) -> None:
        """Set value without triggering the dropdown filter/popup"""
        self._silent = True
        self.var.set(value)
        self._silent = False

    def set_values(self, values: List[str]) -> None:
        self.full_values = list(values)
        self.filtered_values = self.full_values.copy()
        self._update_listbox()

# ==================== TOOLTIP ====================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Arial", 9)).pack()

    def _hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# ==================== MODERN UI ====================
class ModernEditor(ttk.Frame):
    """Modern split-panel editor with left list, middle scrollable editor, right buttons"""
    
    def __init__(self, parent, item_type: str, config: Optional[Dict] = None):
        super().__init__(parent)
        self.item_type = item_type  # 'weapon', 'item', 'scroll'
        self.selected_index: Optional[int] = None
        self.selected_item: Optional[Dict] = None
        self.config = config if config is not None else ConfigManager.load_config()
        self._suppress_selection_event = False
        
        self.setup_ui()
    
    def setup_ui(self):
        """Create responsive 3-panel layout with resizable divider"""
        # Container for main panes + fixed action panel
        content_frame = ttk.Frame(self)
        content_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # RIGHT PANEL - Action Buttons (fixed, always visible, no scrollbar)
        right_frame = ttk.Frame(content_frame, width=120)
        right_frame.pack(side="right", fill="y", padx=(5, 0))
        right_frame.pack_propagate(False)

        # Use PanedWindow for resizable left and middle panels
        paned = tk.PanedWindow(content_frame, orient="horizontal", sashwidth=5)
        paned.pack(side="left", fill="both", expand=True)
        paned.bind("<ButtonRelease-1>", self.save_panel_width)
        
        # LEFT PANEL - Item list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, minsize=LEFT_PANEL_MIN_WIDTH)
        
        ttk.Label(left_frame, text=f"{self.item_type.title()}s").pack(anchor="w")
        self.filter_var = tk.StringVar()
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill="x", pady=5)
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        self.filter_entry.pack(side="left", fill="both", expand=True)
        ttk.Button(filter_frame, text="✕", width=2, command=lambda: self.filter_var.set("")).pack(side="left", fill="y")
        self.filter_var.trace_add("write", lambda *args: self.populate_list())
        
        # Treeview
        columns = self.get_list_columns()
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=30)
        self.setup_treeview_columns(columns)
        
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # MIDDLE PANEL - Editor (scrollable)
        self.editor_frame = ttk.Frame(paned)
        paned.add(self.editor_frame, minsize=200)
        self.editor_frame.grid_rowconfigure(0, weight=1)
        self.editor_frame.grid_columnconfigure(0, weight=1)

        # Plain editor container (no scrollbar)
        self.editor_content = ttk.Frame(self.editor_frame)
        self.editor_content.grid(row=0, column=0, sticky="nsew")
        
        ttk.Label(right_frame, text="Actions", font=("Arial", 10, "bold")).pack(pady=10)
        
        ttk.Button(right_frame, text="Save", command=self.on_save).pack(fill="x", pady=5)
        ttk.Button(right_frame, text="Delete", command=self.on_delete).pack(fill="x", pady=5)
        ttk.Button(right_frame, text="Reset", command=self.on_reset).pack(fill="x", pady=5)
        
        if self.item_type == "item":
            ttk.Button(right_frame, text="Max All", command=self.on_max_all).pack(fill="x", pady=5)
        
        ttk.Button(right_frame, text="Clear", command=self.on_clear_selection).pack(fill="x", pady=5)
        
        # Bind tree selection
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Store paned reference and set initial width
        self.paned = paned
        self.bind("<Map>", lambda _event: self.load_panel_width())
        self.load_panel_width()
        
        self.populate_list()
    
    def save_panel_width(self, event=None):
        """Save the panel width to configuration"""
        if not hasattr(self, 'paned'):
            return
        if len(self.paned.panes()) < 2:
            return
        try:
            width = max(self.paned.sash_coord(0)[0], LEFT_PANEL_MIN_WIDTH)
            self.config["panel_widths"][self.item_type] = width
            ConfigManager.save_config(self.config)
        except TclError:
            return
    
    def load_panel_width(self):
        """Load and apply saved panel width"""
        width = max(self.config.get("panel_widths", {}).get(self.item_type, LEFT_PANEL_MIN_WIDTH), LEFT_PANEL_MIN_WIDTH)
        if not hasattr(self, 'paned'):
            return

        def _apply_sash() -> None:
            if len(self.paned.panes()) < 2:
                return
            if not self.winfo_ismapped() or self.paned.winfo_width() <= 1:
                self.after(50, _apply_sash)
                return
            try:
                self.paned.sash_place(0, width, 0)
            except TclError:
                pass

        self.after_idle(_apply_sash)
    
    def get_list_columns(self) -> Tuple:
        if self.item_type == "weapon":
            return ("slot", "id", "name", "level", "tier")
        elif self.item_type == "item":
            return ("slot", "id", "name", "qty")
        else:  # scroll
            return ("slot", "id", "name", "tier", "level")
    
    def setup_treeview_columns(self, columns):
        widths = {"slot": 40, "id": 60, "name": 150, "level": 50, "tier": 40, "qty": 50}
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=widths.get(col, 60))
    
    def get_items(self) -> List[Dict]:
        if self.item_type == "weapon":
            return save_state.weapons
        elif self.item_type == "item":
            return save_state.items
        else:
            return save_state.scrolls
    
    def populate_list(self, selected_slot: Optional[int] = None):
        self.tree.delete(*self.tree.get_children())
        filter_text = self.filter_var.get().lower()
        items_list = self.get_items()
        
        for item in items_list:
            if item.get('item_id_1', 0) == 0:
                continue
            
            iid_hex = swap_endian_hex(item['item_id_1'])
            name, _ = JSONManager.get_item_name_type(iid_hex)
            
            if filter_text and filter_text not in name.lower():
                continue
            
            if self.item_type == "weapon":
                values = (item['slot'], iid_hex, name, item.get('weapon_level', 0), item.get('weapon_tier', 0))
            elif self.item_type == "item":
                values = (item['slot'], iid_hex, name, item.get('quantity', 0))
            else:  # scroll
                values = (item['slot'], iid_hex, name, item.get('tier', 0), item.get('item_level_1', 0))
            
            self.tree.insert("", "end", iid=item['slot'], values=values)

        if selected_slot is not None:
            self._set_tree_selection(selected_slot)

    def _set_tree_selection(self, slot: int) -> None:
        tree_iid = str(slot)
        if not self.tree.exists(tree_iid):
            return

        self._suppress_selection_event = True
        try:
            self.tree.selection_set(tree_iid)
            self.tree.focus(tree_iid)
            self.tree.see(tree_iid)
        finally:
            self._suppress_selection_event = False

    def refresh_selected_item(self) -> None:
        prev_item_id = self.selected_item.get('item_id_1') if self.selected_item else None

        if prev_item_id is not None:
            items_list = self.get_items()
            for item in items_list:
                if item.get('item_id_1') == prev_item_id and prev_item_id != 0:
                    self.selected_index = item['slot']
                    self.selected_item = item
                    self.populate_list(selected_slot=self.selected_index)
                    self.load_editor()
                    return

        self.selected_index = None
        self.selected_item = None
        self.populate_list()
        self.load_editor()

    def commit_editor_changes(self, refresh_list: bool = True) -> bool:
        if self.selected_item is None:
            return True

        try:
            for key, entry in self.entries.items():
                self.selected_item[key] = int(entry.get())

            if hasattr(self, 'effect_combos'):
                for i, combo in enumerate(self.effect_combos):
                    chosen = combo.get().strip()
                    if chosen:
                        hex_id = chosen.split(" - ", 1)[0].strip()
                        if hex_id:
                            self.selected_item[f'effect_id_{i+1}'] = int(hex_id, 16)

                    mag_val = self.effect_mags[i].get().strip()
                    if mag_val:
                        self.selected_item[f'effect_magnitude_{i+1}'] = int(mag_val)

            if refresh_list and self.selected_index is not None:
                self.populate_list(selected_slot=self.selected_index)

            return True
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid value: {e}")
            self.load_editor()
            return False
    
    def on_tree_select(self, event):
        if self._suppress_selection_event:
            return

        sel = self.tree.selection()
        if not sel:
            return
        
        idx = int(sel[0])
        if idx == self.selected_index:
            return

        previous_index = self.selected_index
        if previous_index is not None and not self.commit_editor_changes(refresh_list=False):
            self._set_tree_selection(previous_index)
            return

        self.selected_index = idx
        self.selected_item = self.get_items()[idx]
        self.populate_list(selected_slot=idx)
        
        self.load_editor()
    
    def load_editor(self):
        """Load editor fields based on item type using config-driven approach"""
        # Clear previous widgets
        for widget in self.editor_content.winfo_children():
            widget.destroy()
        
        if self.selected_item is None:
            ttk.Label(self.editor_content, text="Select an item").pack()
            return
        
        # Properties frame
        props_frame = ttk.LabelFrame(self.editor_content, text="Properties", padding=10)
        props_frame.pack(fill="x", padx=5, pady=5)
        
        self.entries = {}
        
        # Use config-driven approach
        fields = EDITOR_FIELDS.get(self.item_type, [])
        self._load_editor_fields(props_frame, fields)
        
        # Load effects for weapon and scroll
        if self.item_type in ("weapon", "scroll"):
            self._load_effects_editor()
    
    def _load_editor_fields(self, parent, fields: List[Tuple[str, str]]):
        """Generic method to load editor fields from config"""
        for i, (key, label) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=3)
            e = ttk.Entry(parent, width=25)
            e.grid(row=i, column=1, sticky="w", padx=5, pady=3)
            self.entries[key] = e
            e.insert(0, self.selected_item.get(key, 0))
    
    def _load_effects_editor(self):
        """Load effects section for weapons and scrolls"""
        effects_frame = ttk.LabelFrame(self.editor_content, text="Effects", padding=10)
        effects_frame.pack(fill="x", padx=5, pady=5)
        
        self.effect_combos = []
        self.effect_mags = []
        
        effect_list = JSONManager.get_effect_dropdown_list()
        
        for i in range(7):
            ttk.Label(effects_frame, text=f"Effect {i+1}:").grid(row=i, column=0, sticky="w", padx=5, pady=3)
            combo = SearchableCombobox(effects_frame, width=40, values=effect_list)
            combo.grid(row=i, column=1, sticky="w", padx=5, pady=3)
            self.effect_combos.append(combo)
            
            # Match original: format as 8-char hex, take last 4 chars
            effect_id = int(self.selected_item.get(f'effect_id_{i+1}', 0))
            hex_id = f"{effect_id:08X}"[-4:]
            for item in effect_list:
                if item.startswith(hex_id):
                    combo.set_silent(item)
                    break
            
            ttk.Label(effects_frame, text="Mag:").grid(row=i, column=2, sticky="w", padx=5)
            mag = ttk.Entry(effects_frame, width=12)
            mag.grid(row=i, column=3, sticky="w", padx=5, pady=3)
            mag.insert(0, self.selected_item.get(f'effect_magnitude_{i+1}', 0))
            self.effect_mags.append(mag)
    
    def on_save(self):
        if self.selected_item is not None and not self.commit_editor_changes(refresh_list=True):
            return

        FileManager.save_file()
    
    def on_delete(self):
        if self.selected_item is None:
            return
        
        if messagebox.askyesno("Confirm", f"Delete {self.item_type}?"):
            self.selected_item['item_id_1'] = 0
            if self.item_type == "item":
                self.selected_item['quantity'] = 0
            self.selected_index = None
            self.selected_item = None
            self.populate_list()
            self.load_editor()
    
    def on_reset(self):
        if self.selected_index is not None:
            self.load_editor()
    
    def on_clear_selection(self):
        self.tree.selection_remove(self.tree.selection())
        self.selected_index = None
        self.selected_item = None
        self.load_editor()
    
    def on_max_all(self):
        if self.item_type != "item":
            return
        
        if messagebox.askyesno("Confirm", "Set all items to 9999?"):
            count = 0
            for item in save_state.items:
                if item['item_id_1'] != 0:
                    item['quantity'] = 9999
                    count += 1
            self.populate_list()
            messagebox.showinfo("Success", f"Maxed {count} items!")

# ==================== MAIN APPLICATION ====================
class Nioh2EditorModern:
    def __init__(self, root):
        global APP_INSTANCE
        self.root = root
        self.config = ConfigManager.load_config()
        APP_INSTANCE = self
        self.root.title("Nioh 2 Save Editor - Modernized")
        self.root.geometry(self.config.get("window_geometry", "1400x800"))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.status_clear_after_id = None
        
        # Setup style
        style = ttk.Style()
        style.theme_use('clam')

        self.open_icon = self.create_open_icon()
        self.save_icon = self.create_save_icon()
        
        # Toolbar
        self.setup_toolbar()
        
        # Main notebook
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create tabs
        self.tab_weapons = ModernEditor(self.notebook, "weapon", self.config)
        self.notebook.add(self.tab_weapons, text="Weapons")
        
        self.tab_items = ModernEditor(self.notebook, "item", self.config)
        self.notebook.add(self.tab_items, text="Items")
        
        self.tab_scrolls = ModernEditor(self.notebook, "scroll", self.config)
        self.notebook.add(self.tab_scrolls, text="Scrolls")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        
        self.tab_stats = self.create_stats_tab()
        self.notebook.add(self.tab_stats, text="Stats")

        self.status_label = tk.Label(
            self.root,
            text="",
            bg="#1f2329",
            fg="#f5f7fa",
            padx=12,
            pady=8,
            bd=1,
            relief="solid"
        )
        self.status_label.place_forget()
        
        self.file_loaded = False
        if AUTO_LOAD_LAST_SAVE:
            self.root.after_idle(self.auto_load_last_save)
    
    def setup_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=5, pady=(5, 0))

        open_button = ttk.Button(toolbar, image=self.open_icon, command=self.load_file)
        open_button.pack(side="left", padx=(0, 4))
        ToolTip(open_button, "Open Save File")

        save_button = ttk.Button(toolbar, image=self.save_icon, command=FileManager.save_file)
        save_button.pack(side="left", padx=(0, 4))
        ToolTip(save_button, "Save")

        import_button = ttk.Button(toolbar, text="Import Save", command=import_save)
        import_button.pack(side="left", padx=(0, 4))

    def create_open_icon(self) -> tk.PhotoImage:
        icon = tk.PhotoImage(width=16, height=16)
        icon.put("#c4901f", to=(1, 5, 15, 13))
        icon.put("#e6bf57", to=(2, 6, 14, 12))
        icon.put("#b67e16", to=(3, 3, 8, 6))
        icon.put("#efcc6c", to=(4, 4, 11, 7))
        icon.put("#d89b22", to=(2, 8, 15, 14))
        icon.put("#f2d47b", to=(3, 9, 14, 13))
        icon.put("#9b6610", to=(1, 5, 15, 6))
        icon.put("#9b6610", to=(1, 12, 15, 13))
        icon.put("#9b6610", to=(1, 5, 2, 13))
        icon.put("#9b6610", to=(14, 8, 15, 13))
        return icon

    def create_save_icon(self) -> tk.PhotoImage:
        icon = tk.PhotoImage(width=16, height=16)
        icon.put("#214f9c", to=(2, 2, 14, 14))
        icon.put("#4d86d9", to=(3, 3, 13, 13))
        icon.put("#17396f", to=(10, 2, 13, 6))
        icon.put("#dfe8f7", to=(4, 4, 10, 7))
        icon.put("#ffffff", to=(5, 5, 9, 6))
        icon.put("#d8d8d8", to=(4, 9, 12, 12))
        icon.put("#f4f4f4", to=(5, 10, 11, 11))
        icon.put("#17396f", to=(2, 2, 14, 3))
        icon.put("#17396f", to=(2, 13, 14, 14))
        icon.put("#17396f", to=(2, 2, 3, 14))
        icon.put("#17396f", to=(13, 2, 14, 14))
        return icon
    
    def load_file(self, file_path: Optional[str] = None):
        if FileManager.open_file(file_path):
            InventoryManager.load_weapons()
            InventoryManager.load_items()
            InventoryManager.load_scrolls()
            
            self.tab_weapons.refresh_selected_item()
            self.tab_items.refresh_selected_item()
            self.tab_scrolls.refresh_selected_item()
            
            self.update_stats_display()
            self.file_loaded = True

            opened_path = FileManager.last_opened_file_path
            if opened_path is not None:
                self.config["last_save_path"] = str(opened_path)
                ConfigManager.save_config(self.config)

            if SHOW_LOAD_SUCCESS_POPUP:
                messagebox.showinfo("Success", 
                    f"Loaded {save_state.mode} save\n"
                    f"{len([w for w in save_state.weapons if w['item_id_1'] != 0])} weapons\n"
                    f"{len([i for i in save_state.items if i['item_id_1'] != 0])} items\n"
                    f"{len([s for s in save_state.scrolls if s['item_id_1'] != 0])} scrolls")

    def auto_load_last_save(self) -> None:
        last_save_path = self.config.get("last_save_path", "")
        if not last_save_path:
            return
        save_path = Path(last_save_path)
        if not save_path.exists():
            return
        self.load_file(str(save_path))

    def on_tab_changed(self, _event=None) -> None:
        current_tab = self.notebook.select()
        current_widget = self.notebook.nametowidget(current_tab)
        if hasattr(current_widget, 'load_panel_width'):
            current_widget.load_panel_width()

    def commit_active_editor_changes(self) -> bool:
        current_tab = self.notebook.select()
        if not current_tab:
            return True

        current_widget = self.notebook.nametowidget(current_tab)
        if isinstance(current_widget, ModernEditor):
            return current_widget.commit_editor_changes(refresh_list=True)

        return True

    def show_status_message(self, message: str) -> None:
        self.status_label.config(text=message)
        self.status_label.lift()
        self.status_label.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")

        if self.status_clear_after_id is not None:
            self.root.after_cancel(self.status_clear_after_id)

        self.status_clear_after_id = self.root.after(5000, self.clear_status_message)

    def clear_status_message(self) -> None:
        self.status_label.place_forget()
        self.status_clear_after_id = None

    def persist_window_state(self) -> None:
        self.config["window_geometry"] = self.root.geometry()

        current_tab = self.notebook.select()
        if current_tab:
            current_widget = self.notebook.nametowidget(current_tab)
            if hasattr(current_widget, 'save_panel_width'):
                current_widget.save_panel_width()

        ConfigManager.save_config(self.config)

    def on_close(self) -> None:
        self.persist_window_state()
        self.root.destroy()
    
    def create_stats_tab(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)
        
        stats_frame = ttk.LabelFrame(frame, text="Character Stats", padding=10)
        stats_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.stat_entries = {}
        stats = get_stat_definitions()
        
        half = (len(stats) + 1) // 2
        
        # Left column
        for i, (name, offset, size) in enumerate(stats[:half]):
            ttk.Label(stats_frame, text=name).grid(row=i, column=0, sticky="w", padx=10, pady=5)
            e = ttk.Entry(stats_frame, width=20)
            e.grid(row=i, column=1, sticky="w", padx=10, pady=5)
            self.stat_entries[name] = (e, offset, size)
        
        # Right column
        for i, (name, offset, size) in enumerate(stats[half:]):
            ttk.Label(stats_frame, text=name).grid(row=i, column=2, sticky="w", padx=20, pady=5)
            e = ttk.Entry(stats_frame, width=20)
            e.grid(row=i, column=3, sticky="w", padx=10, pady=5)
            self.stat_entries[name] = (e, offset, size)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Load Stats", command=self.update_stats_display).pack(side="left", padx=20)
        ttk.Button(btn_frame, text="Save Stats", command=self.save_stats).pack(side="left", padx=20)
        
        return frame
    
    def update_stats_display(self):
        if not save_state.data:
            return
        
        for name, (entry, offset, size) in self.stat_entries.items():
            value = find_value_at_offset(save_state.data, offset, size)
            entry.delete(0, tk.END)
            entry.insert(0, value if value is not None else 0)
    
    def save_stats(self):
        if not save_state.data:
            messagebox.showwarning("Warning", "No file loaded")
            return
        
        try:
            for name, (entry, offset, size) in self.stat_entries.items():
                value = int(entry.get())
                save_state.data[offset:offset+size] = write_le(value, size)
            messagebox.showinfo("Success", "Stats updated!")
        except ValueError:
            messagebox.showerror("Error", "Invalid value entered")

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = Nioh2EditorModern(root)
    root.mainloop()
