from solana.rpc.api import Client
from solders.keypair import Keypair #type: ignore

PRIV_KEY = "PRIV_KEY"
RPC = "RPC"
WSS_URL = "WSS"
UNIT_BUDGET =  100_000
UNIT_PRICE =  1_000_000

#BUY SETTINGS
sol_in = .001
slippage = 5

#SELL SETTINGS
percentage = 100
slippage = 5


client = Client(RPC)
payer_keypair = Keypair.from_base58_string(PRIV_KEY)
