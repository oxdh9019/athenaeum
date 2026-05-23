import asyncio
import sys
sys.path.insert(0, '/Volumes/Ollama-Models/Athenaeum/v0.3/server')
sys.path.insert(0, '/Volumes/Ollama-Models/Athenaeum/v0.4')

from utils.ollama_client import OllamaLLMClient
from worldsmith import Worldsmith, CharacterBatchRequest

async def test():
    print('Testing character generation...')
    local_llm = OllamaLLMClient()
    
    ws = Worldsmith(cloud_llm=local_llm, local_llm=local_llm)
    
    req = CharacterBatchRequest(
        world_description='大唐盛世的长安',
        locations=['朱雀大街', '西市', '大明宫'],
        num_characters=3
    )
    
    try:
        chars = await ws.generate_characters(req)
        print(f'Generated {len(chars)} characters:')
        for c in chars:
            print(f'{c.name} - {c.identity_tags.primary}')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        print(traceback.format_exc())

asyncio.run(test())
