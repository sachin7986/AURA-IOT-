import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
from core.router import route_command

async def _test():
    print(f"API Key detected: {'GROQ_API_KEY' in os.environ}\n")
    
    print("=== Test 1: Get Date ===")
    r = await route_command("what is today's date")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")
    
    print("=== Test 2: Get Time ===")
    r = await route_command("what time is it")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")
    
    print("=== Test 3: Volume Set ===")
    r = await route_command("set volume to 40")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")
    
    print("=== Test 4: Volume Up ===")
    r = await route_command("volume up")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")
    
    print("=== Test 5: Battery ===")
    r = await route_command("check battery")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")
    
    print("=== Test 6: Mute ===")
    r = await route_command("mute")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")

    print("=== Test 7: Unmute ===")
    r = await route_command("unmute")
    print(f"  Engine: {r['engine']}, Response: {r['response']}\n")
    
    print("=== ALL TESTS COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(_test())
