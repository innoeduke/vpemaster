"""
Blockchain service for recording and verifying education level completions.
Uses a smart contract on the Sepolia testnet.
"""
import os
import json
import hashlib
import logging
from datetime import datetime

import requests as http_requests
from web3 import Web3

logger = logging.getLogger(__name__)


class BlockchainService:
    """Service for interacting with the Level Tracker smart contract."""

    _tx_blocks_cache = None              # Etherscan block list cache
    _CHUNK_SIZE = 10                     # Alchemy free-tier eth_getLogs limit
    _SEPOLIA_CHAIN_ID = 11155111

    # ── Connection ───────────────────────────────────────

    @staticmethod
    def _get_web3_and_contract():
        """
        Initialise Web3 + contract instance.
        Returns (w3, contract) or raises RuntimeError.
        """
        rpc_url = os.environ.get("SEPOLIA_RPC_URL")
        contract_address = os.environ.get("LEVEL_TRACKER_CONTRACT_ADDRESS")

        if not rpc_url or not contract_address:
            raise RuntimeError(
                "Blockchain settings missing "
                "(SEPOLIA_RPC_URL / LEVEL_TRACKER_CONTRACT_ADDRESS)."
            )

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise RuntimeError("Failed to connect to the Sepolia RPC URL.")

        abi_path = os.path.join(
            os.path.dirname(__file__), "..", "level_tracker_abi.json"
        )
        abi_path = os.path.normpath(abi_path)
        if not os.path.exists(abi_path):
            raise RuntimeError(f"Contract ABI not found at {abi_path}.")

        with open(abi_path, "r") as f:
            abi = json.load(f)

        contract = w3.eth.contract(address=contract_address, abi=abi)
        return w3, contract

    @classmethod
    def deploy_contract(cls):
        """
        Compile and deploy the LevelTracker contract to Sepolia.
        Returns the new contract address and saves the ABI.
        """
        from solcx import compile_standard, install_solc
        install_solc('0.8.0')

        rpc_url = os.environ.get("SEPOLIA_RPC_URL")
        private_key = os.environ.get("WALLET_PRIVATE_KEY")

        if not rpc_url or not private_key:
            raise RuntimeError("Missing SEPOLIA_RPC_URL or WALLET_PRIVATE_KEY")

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise RuntimeError("Failed to connect to the Sepolia RPC URL")

        account = w3.eth.account.from_key(private_key)
        sol_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts", "blockchain", "LevelTracker.sol"
        )
        sol_path = os.path.normpath(sol_path)

        with open(sol_path, "r") as file:
            level_tracker_file = file.read()

        logger.info("Compiling contract...")
        compiled_sol = compile_standard(
            {
                "language": "Solidity",
                "sources": {"LevelTracker.sol": {"content": level_tracker_file}},
                "settings": {
                    "outputSelection": {
                        "*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}
                    }
                },
            },
            solc_version="0.8.0",
        )

        bytecode = compiled_sol["contracts"]["LevelTracker.sol"]["LevelTracker"]["evm"]["bytecode"]["object"]
        abi = compiled_sol["contracts"]["LevelTracker.sol"]["LevelTracker"]["abi"]

        abi_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "app", "level_tracker_abi.json"
        )
        abi_path = os.path.normpath(abi_path)
        with open(abi_path, "w") as file:
            json.dump(abi, file)
        
        logger.info("Saved new ABI to app/level_tracker_abi.json")

        LevelTracker = w3.eth.contract(abi=abi, bytecode=bytecode)
        nonce = w3.eth.get_transaction_count(account.address, "pending")

        transaction = LevelTracker.constructor().build_transaction({
            "chainId": cls._SEPOLIA_CHAIN_ID,
            "gas": 2000000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
            "from": account.address,
        })

        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=private_key)
        
        logger.info("Deploying new LevelTracker contract...")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return tx_receipt.contractAddress

    # ── Etherscan helpers ────────────────────────────────

    @classmethod
    def _get_contract_tx_blocks(cls, contract_address):
        """
        Use Etherscan V2 API to get block numbers that contain transactions
        for this contract.  Returns a sorted list of unique block numbers,
        cached after first call.  Returns None on failure.
        """
        if cls._tx_blocks_cache is not None:
            return cls._tx_blocks_cache

        api_key = os.environ.get("ETHERSCAN_API_KEY", "")
        url = (
            f"https://api.etherscan.io/v2/api"
            f"?chainid={cls._SEPOLIA_CHAIN_ID}"
            f"&module=account&action=txlist"
            f"&address={contract_address}"
            f"&startblock=0&endblock=99999999&sort=asc"
            f"&apikey={api_key}"
        )

        try:
            resp = http_requests.get(url, timeout=10)
            data = resp.json()
            if data.get("status") == "1" and data.get("result"):
                blocks = sorted(
                    set(int(tx["blockNumber"]) for tx in data["result"])
                )
                cls._tx_blocks_cache = blocks
                logger.info(
                    f"Etherscan: found {len(blocks)} unique blocks "
                    f"with contract txns"
                )
                return blocks
            else:
                logger.warning(
                    f"Etherscan API returned no results: "
                    f"{data.get('message')}"
                )
                return None
        except Exception as e:
            logger.warning(f"Etherscan API call failed: {e}")
            return None

    @staticmethod
    def _find_deployment_block(w3, contract_address):
        """Binary-search for the block where the contract was deployed."""
        latest = w3.eth.block_number
        lo, hi = 0, latest
        while lo < hi:
            mid = (lo + hi) // 2
            code = w3.eth.get_code(contract_address, block_identifier=mid)
            if len(code) > 0:
                hi = mid
            else:
                lo = mid + 1
        logger.info(f"Contract deployment block discovered: {lo}")
        return lo

    @staticmethod
    def _compute_hash(member_no, path_name, level):
        """Compute SHA256 hash from member_no + path_name + level."""
        raw = f"{member_no}{path_name}{level}"
        return hashlib.sha256(raw.encode("utf-8")).digest()

    # ── Public API ───────────────────────────────────────

    @staticmethod
    def record_level(member_no, path_name, level, issue_date, user_identifier="System"):
        """
        Record a level completion hash to the smart contract.
        `issue_date` should be a Python datetime.date or datetime.datetime object.
        Returns True if the transaction was sent, False otherwise.
        """
        if not member_no or not path_name or not level or not issue_date:
            logger.warning(
                f"Skipping blockchain record: missing data "
                f"(member_no={member_no}, path_name={path_name}, "
                f"level={level}, issue_date={issue_date})"
            )
            return False

        # Idempotency check: Skip if already verified on-chain
        try:
            status = BlockchainService.verify_level(member_no, path_name, level)
            if status.get('verified'):
                logger.info(f"Idempotency: Level {level} for member {member_no} already recorded and active on-chain. Skipping.")
                return True
        except Exception as e:
            logger.error(f"Error during idempotency check: {e}")
            # Continue recording if check fails, to be safe

        # Convert date to Unix timestamp (seconds)
        if hasattr(issue_date, 'timetuple'):
            import time
            issue_timestamp = int(time.mktime(issue_date.timetuple()))
        else:
            issue_timestamp = int(issue_date)

        private_key = os.environ.get("WALLET_PRIVATE_KEY")
        if not private_key:
            logger.warning(
                "WALLET_PRIVATE_KEY not set. Skipping blockchain record."
            )
            return False

        try:
            w3, contract = BlockchainService._get_web3_and_contract()
            account = w3.eth.account.from_key(private_key)

            completion_hash = BlockchainService._compute_hash(
                member_no, path_name, level
            )

            nonce = w3.eth.get_transaction_count(account.address, "pending")
            transaction = contract.functions.recordLevel(
                completion_hash, user_identifier, issue_timestamp
            ).build_transaction({
                "chainId": BlockchainService._SEPOLIA_CHAIN_ID,
                "gas": 2000000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
                "from": account.address,
            })

            signed_txn = w3.eth.account.sign_transaction(
                transaction, private_key=private_key
            )
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.info(f"Blockchain transaction sent (recordLevel): {w3.to_hex(tx_hash)}")
            return True

        except Exception as e:
            logger.error(f"Failed to record level on blockchain: {e}")
            return False

    @staticmethod
    def revoke_level(member_no, path_name, level, issue_date, user_identifier="System"):
        """
        Revoke a previously recorded level completion on-chain.
        `issue_date` should be a Python datetime.date or datetime.datetime object.
        Returns True if the transaction was sent, False otherwise.
        """
        private_key = os.environ.get("WALLET_PRIVATE_KEY")
        if not private_key:
            return False

        # Convert date to Unix timestamp (seconds)
        if hasattr(issue_date, 'timetuple'):
            import time
            issue_timestamp = int(time.mktime(issue_date.timetuple()))
        else:
            issue_timestamp = int(issue_date)

        try:
            w3, contract = BlockchainService._get_web3_and_contract()
            account = w3.eth.account.from_key(private_key)

            completion_hash = BlockchainService._compute_hash(
                member_no, path_name, level
            )

            nonce = w3.eth.get_transaction_count(account.address, "pending")
            transaction = contract.functions.revokeLevel(
                completion_hash, user_identifier, issue_timestamp
            ).build_transaction({
                "chainId": BlockchainService._SEPOLIA_CHAIN_ID,
                "gas": 2000000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
                "from": account.address,
            })

            signed_txn = w3.eth.account.sign_transaction(
                transaction, private_key=private_key
            )
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.info(f"Blockchain transaction sent (revokeLevel): {w3.to_hex(tx_hash)}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke level on blockchain: {e}")
            return False

    @classmethod
    def verify_level(cls, member_no, path_name, level):
        """
        Verify whether a level completion hash exists on-chain.
        Uses Etherscan to identify relevant blocks, then queries only
        those.  Falls back to chunked scanning if Etherscan is
        unavailable.

        Returns dict:
          { verified: True,  tx_hash, block_number, recorded_time,
            expected_hash }
          { verified: False, expected_hash }
          { verified: False, error: str }
        """
        try:
            w3, contract = cls._get_web3_and_contract()
        except RuntimeError as e:
            return {"verified": False, "error": str(e)}

        contract_address = os.environ.get("LEVEL_TRACKER_CONTRACT_ADDRESS")
        expected_hash = cls._compute_hash(member_no, path_name, level)
        expected_hex = w3.to_hex(expected_hash)

        def _match(recorded_events, revoked_events):
            """Extract result from matching events and build history."""
            history = []
            
            for ev in recorded_events:
                issue_date_str = datetime.fromtimestamp(ev.args.issueDate).strftime("%Y-%m-%d") if hasattr(ev.args, 'issueDate') else "Unknown"
                history.append({
                    "action": "Recorded",
                    "tx_hash": w3.to_hex(ev.transactionHash),
                    "block_number": ev.blockNumber,
                    "transaction_index": ev.transactionIndex,
                    "user": ev.args.user if hasattr(ev.args, 'user') else "System",
                    "time": datetime.fromtimestamp(ev.args.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                    "issue_date": issue_date_str
                })
                
            for ev in revoked_events:
                issue_date_str = datetime.fromtimestamp(ev.args.issueDate).strftime("%Y-%m-%d") if hasattr(ev.args, 'issueDate') else "Unknown"
                history.append({
                    "action": "Revoked",
                    "tx_hash": w3.to_hex(ev.transactionHash),
                    "block_number": ev.blockNumber,
                    "transaction_index": ev.transactionIndex,
                    "user": ev.args.user if hasattr(ev.args, 'user') else "System",
                    "time": datetime.fromtimestamp(ev.args.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                    "issue_date": issue_date_str
                })
                
            if not history:
                return None
                
            # sort in descending order (latest first)
            history.sort(key=lambda x: (x["block_number"], x["transaction_index"]), reverse=True)
            
            latest = history[0]
            is_revoked = latest["action"] == "Revoked"
            
            result = {
                "verified": not is_revoked,
                "revoked": is_revoked,
                "tx_hash": latest["tx_hash"],
                "block_number": latest["block_number"],
                "issue_date": latest["issue_date"],
                "expected_hash": expected_hex,
                "history": history
            }
            if is_revoked:
                result["revoked_user"] = latest["user"]
                result["revoked_time"] = latest["time"]
            else:
                result["recorded_user"] = latest["user"]
                result["recorded_time"] = latest["time"]
                
            return result

        try:
            all_rec_events = []
            all_rev_events = []

            # Strategy 1: Etherscan — query only known tx blocks
            tx_blocks = cls._get_contract_tx_blocks(contract_address)

            if tx_blocks:
                logger.info(
                    f"Querying {len(tx_blocks)} specific blocks "
                    f"for hash {expected_hex}"
                )
                for block_num in tx_blocks:
                    # Look for recording
                    rec_events = contract.events.LevelRecorded.get_logs(
                        fromBlock=block_num,
                        toBlock=block_num,
                        argument_filters={"completionHash": expected_hash},
                    )
                    if rec_events:
                        all_rec_events.extend(rec_events)
                    
                    # Look for revocation
                    rev_events = contract.events.LevelRevoked.get_logs(
                        fromBlock=block_num,
                        toBlock=block_num,
                        argument_filters={"completionHash": expected_hash},
                    )
                    if rev_events:
                        all_rev_events.extend(rev_events)
            else:
                # Strategy 2: Fallback — chunked scan from deployment block
                logger.info("Falling back to chunked block scanning")
                deploy_block = cls._find_deployment_block(w3, contract_address)
                latest_block = w3.eth.block_number

                from_block = deploy_block
                while from_block <= latest_block:
                    to_block = min(
                        from_block + cls._CHUNK_SIZE - 1, latest_block
                    )
                    rec_events = contract.events.LevelRecorded.get_logs(
                        fromBlock=from_block,
                        toBlock=to_block,
                        argument_filters={"completionHash": expected_hash},
                    )
                    if rec_events:
                        all_rec_events.extend(rec_events)

                    rev_events = contract.events.LevelRevoked.get_logs(
                        fromBlock=from_block,
                        toBlock=to_block,
                        argument_filters={"completionHash": expected_hash},
                    )
                    if rev_events:
                        all_rev_events.extend(rev_events)
                        
                    from_block = to_block + 1
            
            result = _match(all_rec_events, all_rev_events)
            if result:
                return result

            return {"verified": False, "expected_hash": expected_hex}

        except Exception as e:
            logger.error(f"Blockchain query failed: {e}")
            return {"verified": False, "error": f"Blockchain query failed: {e}"}

    @classmethod
    def bulk_upload(cls):
        """
        Record all 'level-completion' achievements in the database to the blockchain.
        Skips already recorded achievements via idempotency in record_level.
        """
        from ..models.achievement import Achievement
        import time

        # Get all level-completion achievements
        achievements = Achievement.query.filter_by(
            achievement_type='level-completion'
        ).order_by(Achievement.issue_date.asc()).all()

        results = []
        total = len(achievements)
        skipped = 0
        recorded = 0
        failed = 0

        print(f"Found {total} level-completion achievements to process.")

        for i, ach in enumerate(achievements, 1):
            if not ach.member_id or not ach.path_name or not ach.level:
                skipped += 1
                print(f"  [{i}/{total}] SKIP (missing data) - ID {ach.id}")
                continue
            
            print(f"  [{i}/{total}] Processing: {ach.member_id} - {ach.path_name} L{ach.level} ({ach.issue_date})...", end=" ", flush=True)
            try:
                # record_level handles idempotency check internally
                success = cls.record_level(
                    member_no=ach.member_id,
                    path_name=ach.path_name,
                    level=ach.level,
                    issue_date=ach.issue_date,
                    user_identifier="Bulk Upload"
                )
                if success:
                    recorded += 1
                    print("✓")
                else:
                    failed += 1
                    print("✗")
                results.append({
                    "achievement_id": ach.id,
                    "success": success,
                    "member_id": ach.member_id,
                    "path": ach.path_name,
                    "level": ach.level
                })
                
                # Small delay to prevent nonce collisions if a transaction was actually sent
                time.sleep(1) 
            except Exception as e:
                failed += 1
                print(f"✗ Error: {e}")
                logger.error(f"Bulk Upload failed for {ach.id}: {e}")
                results.append({
                    "achievement_id": ach.id,
                    "success": False,
                    "error": str(e),
                    "member_id": ach.member_id,
                    "path": ach.path_name,
                    "level": ach.level
                })

        print(f"\nDone! Recorded: {recorded}, Skipped: {skipped}, Failed: {failed}, Total: {total}")
        return results


# ── Convenience aliases for backward compatibility ───────
record_level = BlockchainService.record_level
verify_level = BlockchainService.verify_level
