import aiohttp
from bs4 import BeautifulSoup
import asyncio
import json

async def emoji_thing():
    emojis = None
    async with aiohttp.ClientSession() as client:
        async with client.get('https://unicode.org/emoji/charts/full-emoji-list.html') as resp:
            assert resp.status == 200
            soup = BeautifulSoup(await resp.text(), 'html.parser')
            tables = [
                [
                    [td.find('img')['src'] if td.find('img') is not None else td.get_text(strip=False) for td in tr.find_all('td')] 
                    for tr in table.find_all('tr')
                ] 
                for table in soup.find_all('table')
            ]
            emojis = {}
            for table in tables:
                for row in table:
                    if len(row) > 4:
                        moji = row[3].replace('…', '').strip()
                        emojis[row[2]] = moji.replace('data:image/png;base64,', '')
                        
    if emojis:
        with open('emojis.json', 'w') as f:
            f.write(json.dumps(emojis))

if __name__ == "__main__":
    loop = asyncio.new_event_loop();
    asyncio.set_event_loop(loop)
    loop.run_until_complete(emoji_thing())
    loop.close()