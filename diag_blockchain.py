import os
import time
import logging
from dotenv import load_dotenv
from web3 import Web3
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def diag():
    logger.info("Starting Blockchain Diagnostic...")
    load_dotenv()
    
    rpc_url = os.getenv("SEPOLIA_RPC_URL")
    contract_address = os.getenv("LEVEL_TRACKER_CONTRACT_ADDRESS")
    
    logger.info(f"RPC URL: {rpc_url}")
    logger.info(f"Contract: {contract_address}")
    
    if not rpc_url:
        logger.error("SEPOLIA_RPC_URL is missing!")
        return

    # 0. Raw Python Requests Test
    logger.info("Step 0: Testing raw Python requests (Bypassing Web3.py)...")
    try:
        import requests
        start = time.time()
        # Test 1: Simple GET
        resp = requests.get("https://www.google.com", timeout=5)
        logger.info(f"Google GET: {resp.status_code} in {time.time()-start:.2f}s")
        
        # Test 2: Alchemy POST (Same as CURL)
        start = time.time()
        payload = {"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}
        resp = requests.post(rpc_url, json=payload, timeout=10)
        logger.info(f"Alchemy POST Status: {resp.status_code}")
        logger.info(f"Alchemy POST Response: {resp.text[:100]}")
        logger.info(f"Alchemy POST took {time.time()-start:.2f}s")
    except Exception as e:
        logger.error(f"Raw requests failed: {e}")

    # 1. Basic Connection Test
    logger.info("Step 1: Testing Web3.py connection...")
    try:
        # Try forcing a longer timeout and specific provider settings
        from web3 import HTTPProvider
        provider = HTTPProvider(rpc_url, request_kwargs={'timeout': 20})
        w3 = Web3(provider)
        
        start = time.time()
        is_connected = w3.is_connected()
        logger.info(f"w3.is_connected(): {is_connected} (took {time.time()-start:.2f}s)")
        
        if not is_connected:
            logger.info("Attempting to get chain_id directly...")
            try:
                cid = w3.eth.chain_id
                logger.info(f"Chain ID: {cid}")
            except Exception as e:
                logger.error(f"eth_chain_id failed: {e}")
            return
    except Exception as e:
        logger.error(f"Web3 Step 1 failed: {e}")
        return

    # 2. Get Block Number
    logger.info("Step 2: Getting latest block number...")
    try:
        block_num = w3.eth.block_number
        logger.info(f"Latest Block Number: {block_num}")
    except Exception as e:
        logger.error(f"Failed to get block number: {e}")
        return

    # 3. Test Contract Interaction (get_code)
    logger.info("Step 3: Checking contract code...")
    try:
        code = w3.eth.get_code(contract_address)
        logger.info(f"Contract Code Length: {len(code)} bytes")
        if len(code) == 0:
            logger.warning("Contract has no code! Is the address correct?")
    except Exception as e:
        logger.error(f"get_code failed: {e}")

    # 4. Test indexed Event Retrieval (The real bottleneck test)
    logger.info("Step 4: Testing indexed get_logs (The 'Block' test)...")
    # Using a fake but valid-format hash to see if it responds quickly
    fake_hash = "0x" + "0" * 64 
    
    # Try multiple common locations for the ABI
    possible_abi_paths = [
        "app/level_tracker_abi.json",
        "level_tracker_abi.json",
        "../app/level_tracker_abi.json"
    ]
    abi_path = None
    for p in possible_abi_paths:
        if os.path.exists(p):
            abi_path = p
            break
            
    if abi_path:
        logger.info(f"Using ABI from: {abi_path}")
        with open(abi_path, 'r') as f:
            abi = json.load(f)
        contract = w3.eth.contract(address=contract_address, abi=abi)
        
        start_time = time.time()
        try:
            # Query the last 50,000 blocks with a filter
            # This is where the user suspects it hangs
            logger.info(f"Querying LevelRecorded logs for last 50,000 blocks...")
            logs = contract.events.LevelRecorded.get_logs(
                fromBlock=block_num - 50000,
                toBlock=block_num,
                argument_filters={"completionHash": fake_hash}
            )
            elapsed = time.time() - start_time
            logger.info(f"Success! Received {len(logs)} logs in {elapsed:.2f} seconds.")
        except Exception as e:
            logger.error(f"get_logs failed: {e}")
            # Try to extract the response if it's a requests error inside web3
            if hasattr(e, 'response'):
                 logger.error(f"Response Body: {e.response.text}")
            elif "400 Client Error" in str(e):
                 logger.info("This is likely a block range limit. Testing smaller range (2000 blocks)...")
                 try:
                     logs = contract.events.LevelRecorded.get_logs(
                         fromBlock=block_num - 2000,
                         toBlock=block_num,
                         argument_filters={"completionHash": fake_hash}
                     )
                     logger.info(f"Small range query SUCCEEDED. Alchemy limited your block range.")
                 except Exception as e2:
                     logger.error(f"Small range also failed: {e2}")
    else:
        logger.warning(f"Skipping Step 4: ABI file not found at {abi_path}")

    logger.info("Diagnostic Complete.")

if __name__ == "__main__":
    diag()
