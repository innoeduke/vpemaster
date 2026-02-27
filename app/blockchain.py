import os
import json
import hashlib
from datetime import datetime
from web3 import Web3


def _get_web3_and_contract(require_private_key=False):
    """
    Shared helper to initialise Web3 + contract.
    Returns (w3, contract) or raises RuntimeError on missing config.
    """
    rpc_url = os.environ.get("SEPOLIA_RPC_URL")
    contract_address = os.environ.get("LEVEL_TRACKER_CONTRACT_ADDRESS")

    if not rpc_url or not contract_address:
        raise RuntimeError("Blockchain settings missing (SEPOLIA_RPC_URL / LEVEL_TRACKER_CONTRACT_ADDRESS).")

    if require_private_key and not os.environ.get("WALLET_PRIVATE_KEY"):
        raise RuntimeError("WALLET_PRIVATE_KEY is required but not set.")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("Failed to connect to the Sepolia RPC URL.")

    abi_path = os.path.join(os.path.dirname(__file__), "level_tracker_abi.json")
    if not os.path.exists(abi_path):
        raise RuntimeError(f"Contract ABI not found at {abi_path}.")

    with open(abi_path, "r") as f:
        abi = json.load(f)

    contract = w3.eth.contract(address=contract_address, abi=abi)
    return w3, contract


import logging
import requests as http_requests

logger = logging.getLogger(__name__)

# Cache contract transaction blocks to avoid repeated Etherscan lookups
_tx_blocks_cache = None
_CHUNK_SIZE = 10  # Alchemy free-tier limit for eth_getLogs


def _get_contract_tx_blocks(contract_address):
    """
    Use Etherscan API to get all block numbers that have transactions
    for this contract. Returns a sorted list of unique block numbers.
    Results are cached for subsequent calls.
    """
    global _tx_blocks_cache
    if _tx_blocks_cache is not None:
        return _tx_blocks_cache

    api_key = os.environ.get("ETHERSCAN_API_KEY", "")
    url = (
        f"https://api.etherscan.io/v2/api"
        f"?chainid=11155111"
        f"&module=account&action=txlist"
        f"&address={contract_address}"
        f"&startblock=0&endblock=99999999&sort=asc"
        f"&apikey={api_key}"
    )

    try:
        resp = http_requests.get(url, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            blocks = sorted(set(int(tx["blockNumber"]) for tx in data["result"]))
            _tx_blocks_cache = blocks
            logger.info(f"Etherscan: found {len(blocks)} unique blocks with contract txns")
            return blocks
        else:
            logger.warning(f"Etherscan API returned no results: {data.get('message')}")
            return None
    except Exception as e:
        logger.warning(f"Etherscan API call failed: {e}")
        return None


def _find_deployment_block(w3, contract_address):
    """Binary-search for the block where the contract was first deployed."""
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


def verify_level_on_chain(member_no, path_name, level):
    """
    Verify whether a level completion hash exists on-chain.
    Strategy: Use Etherscan to find which blocks have contract txns,
    then query only those blocks. Falls back to chunked scanning if
    Etherscan is unavailable.
    """
    try:
        w3, contract = _get_web3_and_contract()
    except RuntimeError as e:
        return {"verified": False, "error": str(e)}

    contract_address = os.environ.get("LEVEL_TRACKER_CONTRACT_ADDRESS")
    raw_string = f"{member_no}{path_name}{level}"
    expected_hash = hashlib.sha256(raw_string.encode("utf-8")).digest()
    expected_hex = w3.to_hex(expected_hash)

    try:
        # Strategy 1: Etherscan — get exact blocks, query only those
        tx_blocks = _get_contract_tx_blocks(contract_address)

        if tx_blocks:
            logger.info(f"Querying {len(tx_blocks)} specific blocks for hash {expected_hex}")
            for block_num in tx_blocks:
                events = contract.events.LevelRecorded.get_logs(
                    fromBlock=block_num,
                    toBlock=block_num,
                    argument_filters={"completionHash": expected_hash}
                )
                if events:
                    event = events[0]
                    timestamp = event.args.timestamp
                    recorded_time = datetime.fromtimestamp(timestamp)
                    return {
                        "verified": True,
                        "tx_hash": w3.to_hex(event.transactionHash),
                        "block_number": event.blockNumber,
                        "recorded_time": recorded_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "expected_hash": expected_hex,
                    }
            return {"verified": False, "expected_hash": expected_hex}

        # Strategy 2: Fallback — chunked scan from deployment block
        logger.info("Falling back to chunked block scanning")
        deploy_block = _find_deployment_block(w3, contract_address)
        latest_block = w3.eth.block_number

        from_block = deploy_block
        while from_block <= latest_block:
            to_block = min(from_block + _CHUNK_SIZE - 1, latest_block)
            events = contract.events.LevelRecorded.get_logs(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters={"completionHash": expected_hash}
            )
            if events:
                event = events[0]
                timestamp = event.args.timestamp
                recorded_time = datetime.fromtimestamp(timestamp)
                return {
                    "verified": True,
                    "tx_hash": w3.to_hex(event.transactionHash),
                    "block_number": event.blockNumber,
                    "recorded_time": recorded_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "expected_hash": expected_hex,
                }
            from_block = to_block + 1

        return {"verified": False, "expected_hash": expected_hex}

    except Exception as e:
        logger.error(f"Blockchain query failed: {e}")
        return {"verified": False, "error": f"Blockchain query failed: {e}"}


def record_level_completion_on_chain(member_no, path_name, level):
    """
    Records a level completion hash to the smart contract on the Sepolia network.
    
    Hash is generated as SHA256(member_no + path_name + level)
    """
    
    # Validate inputs as requested by the user
    if not member_no or not path_name or not level:
        print(f"Skipping blockchain record: Missing required data (member_no={member_no}, path_name={path_name}, level={level})")
        return False
        
    # Check if we have the necessary credentials
    rpc_url = os.environ.get("SEPOLIA_RPC_URL")
    private_key = os.environ.get("WALLET_PRIVATE_KEY")
    contract_address = os.environ.get("LEVEL_TRACKER_CONTRACT_ADDRESS")
    
    if not (rpc_url and private_key and contract_address):
        print("Blockchain settings missing. Skipping level tracking on chain.")
        return False
        
    try:
        # Load the ABI
        abi_path = os.path.join(os.path.dirname(__file__), "level_tracker_abi.json")
        if not os.path.exists(abi_path):
            print(f"Contract ABI not found at {abi_path}. Ensure it is generated by the deploy script.")
            return False
            
        with open(abi_path, "r") as f:
            abi = json.load(f)

        # Connect to network
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            print("Failed to connect to the Sepolia RPC URL.")
            return False

        account = w3.eth.account.from_key(private_key)
        contract = w3.eth.contract(address=contract_address, abi=abi)

        # Generate the hash
        raw_string = f"{member_no}{path_name}{level}"
        completion_hash = hashlib.sha256(raw_string.encode('utf-8')).digest()

        # Build transaction using the 'pending' nonce so we can send multiple quickly
        nonce = w3.eth.get_transaction_count(account.address, 'pending')
        
        # We use build_transaction to prepare it before signing
        transaction = contract.functions.recordLevel(completion_hash).build_transaction({
            'chainId': 11155111, # Sepolia
            'gas': 2000000,      # A safe limit, will probably use less
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'from': account.address
        })

        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=private_key)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        print(f"Sent blockchain transaction! Hash: {w3.to_hex(tx_hash)}")
        
        # For a web app, we generally don't want to wait synchronously for the transaction to be mined
        # because it can take 15+ seconds. We just return True that it was sent.
        return True

    except Exception as e:
        print(f"An error occurred while tracking level to blockchain: {e}")
        return False
