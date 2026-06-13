import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

load_dotenv()

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

client.create_payload_index(
    collection_name="medibot_chunks",
    field_name="collection",
    field_schema=PayloadSchemaType.KEYWORD,
)

print("✅ Index created on 'collection' field. Ready to search.")