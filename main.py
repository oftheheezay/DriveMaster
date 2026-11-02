from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
import sqlite3

app = FastAPI(
    title="DriveMaster API",
    description="Информационная система управления заказ-нарядами СТО",
    version="1.0.0"
)

DB_NAME = "drivemaster.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            vin TEXT NOT NULL,
            problem_description TEXT NOT NULL,
            total_amount REAL DEFAULT 0.0,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

ALLOWED_STATUSES = [
    "Черновик",
    "Осмотр",
    "Согласование_сметы",
    "В_работе",
    "Ожидание_запчастей",
    "Контроль_качества",
    "Готов_к_выдаче",
    "Закрыт_и_Оплачен",
    "Отменен"
]

class OrderCreate(BaseModel):
    client_name: str = Field(..., example="Иван Петров")
    vin: str = Field(..., min_length=17, max_length=17, example="WAUZZZ8K9BA123456")
    problem_description: str = Field(..., example="Замена тормозных колодок и диагностика подвески")
    total_amount: float = Field(default=0.0, ge=0.0, example=4500.0)

class StatusUpdate(BaseModel):
    status: str = Field(..., example="В_работе")

class OrderResponse(OrderCreate):
    id: int
    status: str

@app.get("/", tags=["Системные"])
def root():
    return {"message": "Система DriveMaster работает. Перейдите на /docs для тестирования."}

@app.post("/orders/", response_model=OrderResponse, tags=["Заказ-наряды"])
def create_order(order: OrderCreate):
    """Создание нового заказ-наряда (начинается со статуса 'Черновик')"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    initial_status = "Черновик"
    
    cursor.execute("""
        INSERT INTO work_orders (client_name, vin, problem_description, total_amount, status)
        VALUES (?, ?, ?, ?, ?)
    """, (order.client_name, order.vin, order.problem_description, order.total_amount, initial_status))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {**order.model_dump(), "id": order_id, "status": initial_status}

@app.get("/orders/", response_model=List[OrderResponse], tags=["Заказ-наряды"])
def get_orders():
    """Получение списка всех заказ-нарядов"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, client_name, vin, problem_description, total_amount, status FROM work_orders")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": r[0],
            "client_name": r[1],
            "vin": r[2],
            "problem_description": r[3],
            "total_amount": r[4],
            "status": r[5]
        }
        for r in rows
    ]

@app.patch("/orders/{order_id}/status", tags=["Заказ-наряды"])
def update_status(order_id: int, payload: StatusUpdate):
    """Смена статуса документа по бизнес-правилам"""
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400, 
            detail=f"Недопустимый статус. Разрешенные: {', '.join(ALLOWED_STATUSES)}"
        )
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM work_orders WHERE id = ?", (order_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Заказ-наряд не найден")
        
    cursor.execute("UPDATE work_orders SET status = ? WHERE id = ?", (payload.status, order_id))
    conn.commit()
    conn.close()
    
    return {"message": "Статус успешно обновлен", "order_id": order_id, "new_status": payload.status}