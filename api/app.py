from fastapi import FastAPI, HTTPException
import pika
import random
import logging
from pika.exceptions import AMQPConnectionError

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_CREDS = pika.PlainCredentials('laura', '123')

def generate_short_id():
    return str(random.randint(100000, 999999))

def get_rabbitmq_channel():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='rabbitmq',
                credentials=RABBITMQ_CREDS,
                heartbeat=600,
                blocked_connection_timeout=300
            )
        )
        channel = connection.channel()
        
        for queue in ['redimensionar', 'marca_agua', 'deteccion']:
            channel.queue_declare(queue=queue, durable=True)
        
        return channel, connection
    except AMQPConnectionError as e:
        logger.error(f"Error de conexión con RabbitMQ: {str(e)}")
        raise HTTPException(status_code=503, detail="Servicio no disponible")

@app.post("/upload")
async def upload_image():
    file_id = generate_short_id()
    
    try:
        channel, connection = get_rabbitmq_channel()
        
        for queue in ['redimensionar', 'marca_agua', 'deteccion']:
            channel.basic_publish(
                exchange='',
                routing_key=queue,
                body=file_id,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={'x-file-id': file_id}
                )
            )
            logger.info(f"Mensaje enviado a cola {queue} para archivo {file_id}")
        
        connection.close()
        return {"id": file_id, "status": "en_proceso"}
    
    except Exception as e:
        logger.error(f"Error al subir imagen: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{id}")
async def get_status(id: str):
    return {
        "id": id,
        "status": "completado",
        "procesos": [
            {"nombre": "redimensionar", "estado": "completado"},
            {"nombre": "marca_agua", "estado": "completado"},
            {"nombre": "deteccion", "estado": "completado"}
        ]
    }