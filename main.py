"""
Convenience entry point for Telegram Media Suite.
Execute simply with:
    python main.py
"""

from run import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
