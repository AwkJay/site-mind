"""One-time setup for Solana devnet notarization (plan §E).

Generates a fresh devnet keypair, prints its base58 secret (paste into
backend/.env as SOLANA_SECRET_KEY) and its pubkey, then attempts a devnet
airdrop so it's immediately usable.

The public devnet airdrop faucet (api.devnet.solana.com's own
`requestAirdrop` RPC) is heavily rate-limited and often returns 429
"airdrop limit reached / faucet has run dry" — a real, common devnet
condition, not a bug here. If the airdrop fails, this script prints the
pubkey and the web faucet URL (https://faucet.solana.com) so you can fund it
manually instead; everything else (SOLANA_SECRET_KEY, the keypair itself)
is still valid and ready to use once funded by any means.

Run: python scripts/solana_setup.py   (from backend/, venv active)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

DEVNET_RPC = "https://api.devnet.solana.com"
AIRDROP_LAMPORTS = 1_000_000_000  # 1 SOL — devnet faucets typically cap per-request amounts around here


async def main() -> None:
    from solders.keypair import Keypair
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed

    kp = Keypair()
    secret_b58 = str(kp)
    pubkey = str(kp.pubkey())

    print("Generated a new Solana devnet keypair.")
    print(f"  Pubkey:        {pubkey}")
    print(f"  Base58 secret: {secret_b58}")
    print()
    print("Add to backend/.env:")
    print(f"  SOLANA_ENABLED=1")
    print(f"  SOLANA_SECRET_KEY={secret_b58}")
    print(f"  SOLANA_RPC_URL={DEVNET_RPC}")
    print(f"  SOLANA_CLUSTER=devnet")
    print()

    async with AsyncClient(DEVNET_RPC) as client:
        try:
            print(f"Requesting a devnet airdrop of {AIRDROP_LAMPORTS / 1e9} SOL...")
            resp = await client.request_airdrop(kp.pubkey(), AIRDROP_LAMPORTS)
            await client.confirm_transaction(resp.value, commitment=Confirmed)
            balance = await client.get_balance(kp.pubkey())
            print(f"Airdrop confirmed. Balance: {balance.value / 1e9} SOL. tx_sig={resp.value}")
        except Exception as exc:
            print(f"Airdrop failed ({exc}).")
            print("The public RPC faucet is commonly rate-limited/dry. Fund this pubkey manually via:")
            print(f"  https://faucet.solana.com  (paste pubkey: {pubkey})")
            print("Re-run `python -c \"from app import notary; ...\"` or check /api/health once funded.")


if __name__ == "__main__":
    asyncio.run(main())
