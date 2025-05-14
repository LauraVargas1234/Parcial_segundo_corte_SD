import pika
import random
import logging

from pika.exceptions import AMQPConnectionError

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_CREDS = pika.PlainCredentials('laura', '123')

def generate_short_id():
    """Genera un ID numérico de 6 dígitos"""
    return str(random.randint(100000, 999999))

def get_rabbitmq_channel():
    """Obtiene canal RabbitMQ con manejo de errores"""
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
def process_task(ch, method, properties, body):
    file_id = body.decode()
    queue_name = method.routing_key
    
    logger.info(f"Procesando {file_id} en cola {queue_name}")
    time.sleep(2)
    
    ch.basic_ack(delivery_tag=method.delivery_tag)
    logger.info(f"Completado {file_id} en {queue_name}")

def connect_rabbitmq():
    """Establece conexión con RabbitMQ con reintentos"""
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host='rabbitmq',
                    credentials=CREDENTIALS,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            return connection
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Intento {attempt + 1} conexión fallida")
            time.sleep(retry_delay)

def main():
    try:
        connection = connect_rabbitmq()
        channel = connection.channel()
        
        setup_queues(channel)
        channel.basic_qos(prefetch_count=1)
        
        for queue in ['redimensionar', 'marca_agua', 'deteccion']:
            channel.basic_consume(
                queue=queue,
                on_message_callback=process_task,
                auto_ack=False
            )
        
        logger.info("Worker iniciado, esperando tareas...")
        channel.start_consuming()
        
    except Exception as e:
        logger.error(f"Error fatal: {str(e)}")
        if 'connection' in locals():
            connection.close()
        raise

if __name__ == '__main__':
    main()