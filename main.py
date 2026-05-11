"""TrimOS — Entry Point."""

from trimos.core.elevation import enable_vt_mode
from trimos.app import main

if __name__ == "__main__":
    enable_vt_mode()
    main()
