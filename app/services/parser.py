import httpx
from datetime import datetime
from typing import List
from xml.etree import ElementTree as ET


class CurrencyParser:
    def __init__(self):
        self.base_url = "http://www.cbr.ru/scripts/XML_daily.asp"
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def fetch_rates(self) -> List[dict]:
        root = ET.fromstring((await self.client.get(self.base_url)).text)
        date = datetime.strptime(root.attrib.get('Date'), '%d.%m.%Y')
        
        return [{
            'char_code': v.find('CharCode').text,
            'name': v.find('Name').text,
            'value': float(v.find('Value').text.replace(',', '.')),
            'date': date
        } for v in root.findall('Valute')]