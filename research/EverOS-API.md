Get started with EverOS API
Follow these steps to integrate long-term memory into your AI Agent

1
Get your API key
Navigate to the API Keys page to create your first key:Go to API Keys

Steps:

Click "Create API Key"
Give your key a descriptive name
Copy and securely store your key
2
Save your first memory
POST/api/v1/memories

Store messages into your memory space for processing and retrieval
Supports text, images, PDFs, HTML and documents in a single request
Run pip install everos before using the Python SDK

# Text message
curl -X POST "https://api.evermind.ai/api/v1/memories" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_demo_001",
    "messages": [
      {
        "role": "user",
        "sender_name": "Demo User",
        "timestamp": 1736935200000,
        "content": "I like black Americano, no sugar, the stronger the better!"
      },
      {
        "role": "assistant",
        "timestamp": 1736935210000,
        "content": "Got it! I will remember your coffee preference."
      }
    ]
  }'

# 1. Acquire presigned URL
curl -X POST 'https://api.evermind.ai/api/v1/object/sign' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "objectList": [
      {
        "fileName": "logo.png",
        "fileType": "image",
        "fileId": "demo_logo_001"
      }
    ]
  }'

# 2. Upload to S3 with fields and credentials from step 1
curl -X POST '<objectSignedInfo.url>' \
  -F 'Content-Type=<objectSignedInfo.fields.Content-Type>' \
  -F 'key=<objectSignedInfo.fields.key>' \
  -F 'policy=<objectSignedInfo.fields.policy>' \
  -F 'x-amz-algorithm=<objectSignedInfo.fields.x-amz-algorithm>' \
  -F 'x-amz-credential=<objectSignedInfo.fields.x-amz-credential>' \
  -F 'x-amz-date=<objectSignedInfo.fields.x-amz-date>' \
  -F 'x-amz-security-token=<objectSignedInfo.fields.x-amz-security-token>' \
  -F 'x-amz-signature=<objectSignedInfo.fields.x-amz-signature>' \
  -F 'file=@/path/to/logo.png'

# 3. Save memory with object key from step 1
curl -X POST 'https://api.evermind.ai/api/v1/memories' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_multimodal_demo",
    "session_id": "session_mm_001",
    "async_mode": false,
    "messages": [
      {
        "role": "user",
        "timestamp": 1711900000000,
        "content": [
          {
            "type": "text",
            "text": "Please take a look at this logo design"
          },
          {
            "type": "image",
            "uri": "<objectKey>",
            "name": "logo.png",
            "ext": "png"
          }
        ]
      },
      {
        "role": "assistant",
        "timestamp": 1711900010000,
        "content": "This logo uses a dark blue tone paired with tech-inspired lines, and the overall design is modern and minimalist, making it very suitable for the brand image of technology products."
      }
    ]
  }'

  
3
Get your memory
Query memory using two different APIs based on your needs.

POST/api/v1/memories/get

Retrieves user's memory data with flexible filters.

Fetches stored memories directly by user ID
Supports filtering by memory type, session, and time range
Returns episodic memory, user profiles, and agent memory
Suitable for scenarios requiring direct access to a user's memory set

curl -X POST "https://api.evermind.ai/api/v1/memories/get" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "memory_type": "episodic_memory",
    "page": 1,
    "page_size": 20,
    "filters": {
      "user_id": "user_demo_001"
    }
  }'


POST/api/v1/memories/search

Searches for relevant memory data using keyword, vector, or hybrid retrieval.

Finds the most relevant memories according to the query text — across text, images, and documents
Returns results with a relevance score
Suitable for scenarios requiring exact matching or semantic retrieval


curl -X POST "https://api.evermind.ai/api/v1/memories/search" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "coffee preference",
    "filters": {
      "user_id": "user_demo_001"
    }
  }'

