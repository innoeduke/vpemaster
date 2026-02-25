import os
import json
import hashlib
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

rpc_url = os.getenv("SEPOLIA_RPC_URL")
contract_address = os.getenv("LEVEL_TRACKER_CONTRACT_ADDRESS")

if not rpc_url or not contract_address:
    print("Error: SEPOLIA_RPC_URL and LEVEL_TRACKER_CONTRACT_ADDRESS must be set in .env")
    exit(1)

# Connect to Sepolia
w3 = Web3(Web3.HTTPProvider(rpc_url))
if not w3.is_connected():
    print("Failed to connect to the Sepolia RPC URL.")
    exit(1)

# Load the ABI from the app module where deploy_contract saved it
abi_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'level_tracker_abi.json')
if not os.path.exists(abi_path):
    print(f"Contract ABI not found at {abi_path}.")
    exit(1)

with open(abi_path, "r") as f:
    abi = json.load(f)

# Connect to the Contract
contract = w3.eth.contract(address=contract_address, abi=abi)

def verify_level_on_chain(member_no, path_name, level):
    """
    Search past blockchain events to verify if the hash exists.
    """
    print(f"Verifying completion for: Member: {member_no} | Path: {path_name} | Level: {level}")
    
    # Generate the hash exactly as the backend does
    raw_string = f"{member_no}{path_name}{level}"
    expected_hash = hashlib.sha256(raw_string.encode('utf-8')).digest()
    
    expected_hex = w3.to_hex(expected_hash)
    print(f"Expected Hash: {expected_hex}")
    
    # Search for events (Note: get_logs across 'latest' can take a moment)
    print("Searching the blockchain for this hash...")
    
    # We query the 'LevelRecorded' event
    event_filter = contract.events.LevelRecorded.create_filter(
        fromBlock=0, # In production this should be the block the contract was deployed
        toBlock='latest'
    )
    
    events = event_filter.get_all_entries()
    
    # Check if our hash is in the emitted events
    for event in events:
        recorded_hash = w3.to_hex(event.args.completionHash)
        if recorded_hash == expected_hex:
            # Found it!
            timestamp = event.args.timestamp
            from datetime import datetime
            recorded_time = datetime.fromtimestamp(timestamp)
            
            print("\n✅ VERIFIED ON BLOCKCHAIN! ✅")
            print(f"Transaction Hash (Log): {w3.to_hex(event.transactionHash)}")
            print(f"Block Number: {event.blockNumber}")
            print(f"Recorded Time: {recorded_time}")
            return True

    print("\n❌ NOT FOUND ON BLOCKCHAIN ❌")
    print(f"The hash {expected_hex} does not exist in the LevelTracker contract.")
    return False

if __name__ == "__main__":
    print("=== Blockchain Data Verification Tool ===")
    member = input("Enter Member No (e.g. 1234567): ")
    path = input("Enter Path Name (e.g. Dynamic Leadership): ")
    level = input("Enter Level (e.g. 1): ")
    
    if member and path and level:
        # Pass the level as an integer since that's what the backend uses when hashing
        verify_level_on_chain(member, path, int(level))
    else:
        print("All inputs are required.")
