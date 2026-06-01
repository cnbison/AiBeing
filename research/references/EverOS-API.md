
## Install the SDK
Get started by installing the EverOS Python SDK via pip.

```bash
pip install everos
export EVEROS_API_KEY=<your_key>
export EVER_OS_BASE_URL=https://api.evermind.ai
```

## Initialize the client
Initialize with your API key to start making requests

```python
from everos import EverOS

client = EverOS(api_key="your-api-key")
memories = client.v1.memories

```

## Add memory
(Store what happened in this session for future retrieval.)
```python
response = memories.add(
    user_id="<string>",
    messages=[
        {
            "role": "<string>",
            "timestamp": "<integer>",
            "content": "<string>"
        }
    ]
)
print(response)

```

## Get memory
(Retrieve stored memories for a given owner, filtered by memory type.)

```python
response = memories.get(
    filters={"user_id": "<string>"},
    memory_type="<string>",
    page=1,
    page_size=10
)
print(response)
```
## Search memory
(Retrieve memories relevant to a query.)

```python
response = memories.search(
    filters={"user_id": "<string>"},
    query="<string>",
    method="<string>",
    top_k=5
)
print(response)
```