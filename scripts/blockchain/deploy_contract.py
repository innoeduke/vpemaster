import os
import json
from dotenv import load_dotenv
from web3 import Web3
from solcx import compile_standard, install_solc

# Install Solidity compiler
install_solc('0.8.0')

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

rpc_url = os.getenv("SEPOLIA_RPC_URL")
private_key = os.getenv("WALLET_PRIVATE_KEY")

if not rpc_url or not private_key:
    print("Error: SEPOLIA_RPC_URL and WALLET_PRIVATE_KEY must be set in .env")
    exit(1)

# Connect to Sepolia
w3 = Web3(Web3.HTTPProvider(rpc_url))
print(f"Connected to Sepolia: {w3.is_connected()}")

# Setup account
account = w3.eth.account.from_key(private_key)

# Read Solidity file
sol_path = os.path.join(os.path.dirname(__file__), "LevelTracker.sol")
with open(sol_path, "r") as file:
    level_tracker_file = file.read()

# Compile the contract
print("Compiling contract...")
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

# Export ABI and Bytecode
compiled_path = os.path.join(os.path.dirname(__file__), "compiled_code.json")
with open(compiled_path, "w") as file:
    json.dump(compiled_sol, file)

# Get ABI and Bytecode
bytecode = compiled_sol["contracts"]["LevelTracker.sol"]["LevelTracker"]["evm"]["bytecode"]["object"]
abi = compiled_sol["contracts"]["LevelTracker.sol"]["LevelTracker"]["abi"]

# Save ABI to a separate file for the backend to use later
abi_path = os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'level_tracker_abi.json')
with open(abi_path, "w") as file:
    json.dump(abi, file)
print("Saved ABI to app/level_tracker_abi.json")

# Create the contract in Python
LevelTracker = w3.eth.contract(abi=abi, bytecode=bytecode)

# Get latest transaction count (nonce)
nonce = w3.eth.get_transaction_count(account.address)
print(f"Deploying from address: {account.address}, nonce: {nonce}")

# Build the transaction
transaction = LevelTracker.constructor().build_transaction({
    "chainId": 11155111, # Sepolia chain ID
    "gasPrice": w3.eth.gas_price,
    "from": account.address,
    "nonce": nonce,
})

# Sign the transaction
signed_txn = w3.eth.account.sign_transaction(transaction, private_key=private_key)

# Send the transaction
print("Deploying contract...")
tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

# Wait for the transaction to be mined
print(f"Waiting for transaction {w3.to_hex(tx_hash)} to be mined...")
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print(f"Done! Contract deployed to {tx_receipt.contractAddress}")
print(f"\nIMPORTANT: Add this line to your .env file:")
print(f"LEVEL_TRACKER_CONTRACT_ADDRESS={tx_receipt.contractAddress}")
