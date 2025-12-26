import asyncio
from sqlmodel import select, Session
from app.services.parser import CurrencyParser
from app.db.models import CurrencyRate
from app.ws.manager import WebSocketManager
from app.nats.manager import NATSManager


class BackgroundTaskManager:
    def __init__(self):
        self.task_running = False
        self.task_interval = 30
        self.parser = CurrencyParser()
        self.last_run = None

    async def run_task(self, session: Session, ws_manager: WebSocketManager, nats_manager: NATSManager):
        self.task_running = True

        try:
            rates_data = await self.parser.fetch_rates()

            new_count = 0
            update_count = 0

            for rate_data in rates_data:
                stmt = select(CurrencyRate).where(
                    CurrencyRate.char_code == rate_data['char_code'],
                    CurrencyRate.date == rate_data['date']
                )
                existing = session.exec(stmt).first()

                if existing:
                    existing.value = rate_data['value']
                    session.add(existing)
                    update_count += 1
                else:
                    session.add(CurrencyRate(**rate_data))
                    new_count += 1

            session.commit()

            message = {
                "new": new_count,
                "updated": update_count,
                "total": len(rates_data)
            }

            await nats_manager.publish("currency.updates", message)

        finally:
            self.task_running = False

    async def start_periodic_task(self, session: Session, ws_manager: WebSocketManager, nats_manager: NATSManager):
        while True:
            await self.run_task(session, ws_manager, nats_manager)
            await asyncio.sleep(self.task_interval)