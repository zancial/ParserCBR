import json
import asyncio
from datetime import datetime
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, create_engine, Session, select

from app.db.models import CurrencyRate, CurrencyRateCreate, CurrencyRateUpdate,CurrencyRateResponse
from app.ws.manager import WebSocketManager
from app.nats.manager import NATSManager
from app.tasks.background_task import BackgroundTaskManager

# ============ НАСТРОЙКА БД ============

DATABASE_URL = "sqlite:///./currency.db"
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

# ======== ЖИЗНЕННЫЙ ЦИКЛ ПРИЛОЖЕНИЯ ========


ws_manager = WebSocketManager()
nats_manager = NATSManager()
task_manager = BackgroundTaskManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    await nats_manager.connect()

    async def nats_message_handler(msg):
        data = json.loads(msg.data.decode())
        if 'char_code' in data and 'name' in data and 'value' in data:
            with Session(engine) as session:
                new_rate = CurrencyRate(
                    char_code=data['char_code'],
                    name=data['name'],
                    value=data['value'],
                    date=datetime.now()
                )
                session.add(new_rate)
                session.commit()

        await ws_manager.broadcast_json(data)

    await nats_manager.subscribe("currency.updates", nats_message_handler)

    async def start_background_tasks():
        with Session(engine) as session:
            await task_manager.start_periodic_task(session, ws_manager, nats_manager)

    task = asyncio.create_task(start_background_tasks())

    yield

    task.cancel()
    await nats_manager.close()

# ============ КОНФИГУРАЦИЯ FASTAPI ============

app = FastAPI(
    title="Курсы валют API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============ ЭНДПОИНТЫ ============


@app.get("/currency", response_model=List[CurrencyRateResponse])
async def get_currency_rates(
    session: Session = Depends(get_session)
):
    rates = session.exec(select(CurrencyRate)).all()

    rates_data = [
        {
            "id": rate.id,
            "char_code": rate.char_code,
            "name": rate.name,
            "value": rate.value,
            "date": rate.date.isoformat() if rate.date else None
        }
        for rate in rates
    ]

    asyncio.create_task(nats_manager.publish("currency.updates", rates_data))

    return rates


@app.get("/currency/{id}", response_model=CurrencyRateResponse)
async def get_currency_rate(
    id: int,
    session: Session = Depends(get_session),
):
    rate = session.get(CurrencyRate, id)
    if not rate:
        raise HTTPException(status_code=404, detail="Курс валюты не найден")

    message = {
        "type": "currency_rate_get",
        "id": rate.id,
        "char_code": rate.char_code,
        "value": rate.value,
        "timestamp": datetime.now().isoformat()
    }

    asyncio.create_task(nats_manager.publish("currency.updates", message))

    return rate


@app.post("/currency", response_model=CurrencyRateResponse, status_code=201)
async def create_currency_rate(
    rate: CurrencyRateCreate,
    session: Session = Depends(get_session)
):
    db_rate = CurrencyRate(
        **rate.dict(),
        date=datetime.now()
    )

    session.add(db_rate)
    session.commit()
    session.refresh(db_rate)

    message = {
        "type": "currency_rate_created",
        "id": db_rate.id,
        "char_code": db_rate.char_code,
        "value": db_rate.value,
        "timestamp": datetime.now().isoformat()
    }

    asyncio.create_task(nats_manager.publish("currency.updates", message))

    return db_rate


@app.patch("/currency/{id}", response_model=CurrencyRateResponse)
async def update_currency_rate(
    id: int,
    rate_update: CurrencyRateUpdate,
    session: Session = Depends(get_session),
    nats_manager: NATSManager = Depends(lambda: nats_manager)
):

    db_rate = session.get(CurrencyRate, id)
    if not db_rate:
        raise HTTPException(status_code=404, detail="Курс валюты не найден")

    update_data = rate_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_rate, field, value)

    session.add(db_rate)
    session.commit()
    session.refresh(db_rate)

    message = {
        "type": "currency_rate_updated",
        "id": db_rate.id,
        "char_code": db_rate.char_code,
        "value": db_rate.value,
        "timestamp": datetime.now().isoformat()
    }

    asyncio.create_task(nats_manager.publish("currency.updates", message))

    return db_rate


@app.delete("/currency/{id}", status_code=204)
async def delete_currency_rate(
    id: int,
    session: Session = Depends(get_session),
    nats_manager: NATSManager = Depends(lambda: nats_manager)
):
    db_rate = session.get(CurrencyRate, id)
    if not db_rate:
        raise HTTPException(status_code=404, detail="Курс валюты не найден")

    session.delete(db_rate)
    session.commit()

    message = {
        "type": "currency_rate_deleted",
        "id": id,
        "char_code": db_rate.char_code,
        "timestamp": datetime.now().isoformat()
    }

    asyncio.create_task(nats_manager.publish("currency.updates", message))


@app.post("/tasks/run")
async def run_background_task(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    background_tasks.add_task(
        task_manager.run_task,
        session,
        ws_manager,
        nats_manager
    )

    return {"message": "Фоновая задача запущена"}


# ============ ЭНДПОИНТ WEBSOCKET ============


@app.websocket("/ws/currency")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Просто слушаем соединение
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)