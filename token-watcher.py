import asyncio
import base64
import json
import struct
import base58
import websockets

class TokenWatcher:
    def __init__(self, wss_url):
        self.wss_url = wss_url
        self.ws = None
        self.subscribed_wallets = set()
        self.next_subscription_id = 1
        self.subscription_ids = {}  # wallet -> subscription id

    async def connect(self):
        self.ws = await websockets.connect(self.wss_url)
        print("Connected to WSS")
        # При подключении заново подписываемся на все адреса
        for wallet in self.subscribed_wallets:
            await self._send_subscribe(wallet)

    async def _send_subscribe(self, wallet):
        sub_id = self.next_subscription_id
        self.next_subscription_id += 1
        subscription_request = {
            "jsonrpc": "2.0",
            "id": sub_id,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [wallet]},
                {"commitment": "finalized"}
            ]
        }
        await self.ws.send(json.dumps(subscription_request))
        self.subscription_ids[wallet] = sub_id
        print(f"Subscribed to wallet: {wallet} with subscription id {sub_id}")

    async def subscribe_wallet(self, wallet):
        if wallet in self.subscribed_wallets:
            print(f"Already subscribed to {wallet}")
            return
        self.subscribed_wallets.add(wallet)
        if self.ws:
            await self._send_subscribe(wallet)

    def parse_create_instruction(self, data):
        if len(data) < 8:
            return None
        offset = 8
        parsed_data = {}
        fields = [
            ("name", "string"),
            ("symbol", "string"),
            ("uri", "string"),
            ("mint", "publicKey"),
            ("bondingCurve", "publicKey"),
            ("user", "publicKey"),
            ("creator", "publicKey"),
        ]
        try:
            for field_name, field_type in fields:
                if field_type == "string":
                    length = struct.unpack("<I", data[offset:offset + 4])[0]
                    offset += 4
                    value = data[offset:offset + length].decode("utf-8")
                    offset += length
                elif field_type == "publicKey":
                    value = base58.b58encode(data[offset:offset + 32]).decode("utf-8")
                    offset += 32
                parsed_data[field_name] = value
            return parsed_data
        except:
            return None

    def handle_message(self, message):
        try:
            data = json.loads(message)
            if data.get("method") == "logsNotification":
                log_data = data["params"]["result"]["value"]
                logs = log_data.get("logs", [])

                if any("Program log: Instruction: Create" in log for log in logs):
                    for log in logs:
                        if "Program data:" in log:
                            encoded_data = log.split(": ")[1]
                            decoded_data = base64.b64decode(encoded_data)
                            parsed = self.parse_create_instruction(decoded_data)
                            if parsed and "name" in parsed:
                                print(f"\nSignature: {log_data.get('signature')}")
                                for k, v in parsed.items():
                                    print(f"{k}: {v}")
                                print("---" * 20)
        except Exception as e:
            print(f"Error processing message: {e}")

    async def listen_ws(self):
        try:
            async for message in self.ws:
                self.handle_message(message)
        except websockets.ConnectionClosed:
            print("Connection closed!")

    async def ping_loop(self):
        while True:
            try:
                await asyncio.sleep(60)  # раз в минуту
                await self.ws.ping()
            except Exception as e:
                print(f"Ping failed: {e}")
                print("Попытка переподключения...")
                await self.reconnect()

    async def reconnect(self):
        try:
            await self.ws.close()
        except:
            pass
        while True:
            try:
                await self.connect()
                print("Reconnected!")
                break
            except Exception as e:
                print(f"Reconnect failed: {e}")
                await asyncio.sleep(5)  # ждем 5 секунд и пытаемся снова

    async def input_loop(self):
        print("Введите адреса кошельков для подписки. Для выхода введите 'exit'")
        while True:
            wallet = await asyncio.to_thread(input, "> ")
            wallet = wallet.strip()
            if wallet.lower() == "exit":
                print("Выход...")
                await self.ws.close()
                break
            if wallet:
                await self.subscribe_wallet(wallet)

    async def run(self):
        await self.connect()
        listener_task = asyncio.create_task(self.listen_ws())
        input_task = asyncio.create_task(self.input_loop())
        ping_task = asyncio.create_task(self.ping_loop())
        done, pending = await asyncio.wait(
            [listener_task, input_task, ping_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

if __name__ == "__main__":
    watcher = TokenWatcher("wss-url")
    asyncio.run(watcher.run())
