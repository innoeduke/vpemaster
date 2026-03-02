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

    # 5. Test Smart Filtering (The Fix)
    logger.info("Step 5: Testing Smart Filtering (Etherscan + specific blocks)...")
    etherscan_api_key = os.getenv("ETHERSCAN_API_KEY")
    if not etherscan_api_key:
        logger.error("ETHERSCAN_API_KEY is missing! Cannot test Step 5.")
    else:
        try:
            import requests as http_requests
            url = (
                f"https://api.etherscan.io/v2/api"
                f"?chainid=11155111" # Sepolia
                f"&module=account&action=txlist"
                f"&address={contract_address}"
                f"&startblock=0&endblock=99999999&sort=asc"
                f"&apikey={etherscan_api_key}"
            )
            logger.info("Quering Etherscan for contract activity...")
            resp = http_requests.get(url, timeout=10)
            data = resp.json()
            if data.get("status") == "1" and data.get("result"):
                blocks = sorted(set(int(tx["blockNumber"]) for tx in data["result"]))
                logger.info(f"Etherscan found activity in {len(blocks)} unique blocks.")
                
                if blocks:
                    target_block = blocks[-1]
                    logger.info(f"Querying Alchemy for the most recent active block: {target_block}")
                    start_time = time.time()
                    # Query ONLY the specific block
                    logs = contract.events.LevelRecorded.get_logs(
                        fromBlock=target_block,
                        toBlock=target_block,
                        argument_filters={"completionHash": fake_hash}
                    )
                    elapsed = time.time() - start_time
                    logger.info(f"SUCCESS! Smart Query (range=1) completed in {elapsed:.2f} seconds.")
                else:
                    logger.warning("No activity found on Etherscan for this contract.")
            else:
                logger.error(f"Etherscan API error: {data.get('message')}")
        except Exception as e:
            logger.error(f"Smart Filtering test failed: {e}")

    logger.info("Diagnostic Complete.")

if __name__ == "__main__":
    diag()
