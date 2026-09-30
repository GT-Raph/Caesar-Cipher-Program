"""Convenient source-tree launcher; packaged apps use src/main.py."""
import flet as ft
from src.cipher_vault.app import main

if __name__ == '__main__':
    ft.run(main)
